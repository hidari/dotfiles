#!/usr/bin/env bats
# =============================================================================
# gh-token-shim (共有判定層 lib.sh と入口の shim) のテスト
# =============================================================================

load test_helper

bats_require_minimum_version 1.5.0

LIB="$REPO_ROOT/scripts/gh-token-shim/lib.sh"
SHIM_SOURCE="$REPO_ROOT/scripts/gh-token-shim/gh"

setup() {
    # shellcheck source=/dev/null
    source "$LIB"
    # ghts_scan が読む変数。呼び出し元の環境の値で結果が変わらないよう外す
    unset GH_REPO
    setup_shim_fixture
}

# -----------------------------------------------------------------------------
# 入口の shim 用の fixture
# -----------------------------------------------------------------------------

# shim を本番と同じ形 (symlink) で置き、偽の gh / security / op / git を別のディレクトリに置く。
# 既定の持ち主 (home) を acme / bob と別にしてあるのは、同じ値だと「origin から決めた」と
# 「既定へ落ちた」が区別できず、持ち主の解決を壊しても緑になるため。
setup_shim_fixture() {
    SHIM_DIR="$BATS_TEST_TMPDIR/shim"
    FAKE_DIR="$BATS_TEST_TMPDIR/fakes"
    SHIM_LOG="$BATS_TEST_TMPDIR/log"
    SHIM_HOME="$BATS_TEST_TMPDIR/home"
    SHIM_PLAIN="$BATS_TEST_TMPDIR/plain"
    SHIM_REPO="$BATS_TEST_TMPDIR/repo"
    SHIM_CONF="$BATS_TEST_TMPDIR/ghts.conf"
    SHIM_PATH="$SHIM_DIR:$FAKE_DIR:/usr/bin:/bin"
    SHIM_ENV=()
    SHIM_RUN_OPTS=()
    mkdir -p "$SHIM_DIR" "$FAKE_DIR" "$SHIM_LOG" "$SHIM_HOME" "$SHIM_PLAIN"
    ln -s "$SHIM_SOURCE" "$SHIM_DIR/gh"
    ln -s "$LIB" "$SHIM_DIR/lib.sh"
    printf '%s\n' 'vault=TestVault' 'default_owner=home' \
        'owner=acme' 'owner=bob' 'owner=home' >"$SHIM_CONF"

    # 本物の代わり。渡された GH_TOKEN と引数を1行に1つずつ残す ($* では "a b" と
    # 2引数を区別できない)。BYPASSED_SHIM は「PATH に shim が残ったまま呼ばれた」印で、
    # 出るときは配線が壊れていて shim は一度も走っていない。
    cat >"$FAKE_DIR/gh" <<'FAKE'
#!/bin/sh
set +x
{
    case ":$PATH:" in
    *":$GHTS_TEST_SHIM_DIR:"*) echo BYPASSED_SHIM ;;
    *) echo REAL_GH_RAN ;;
    esac
    printf 'GH_TOKEN=[%s]\n' "${GH_TOKEN-<unset>}"
    printf 'GITHUB_TOKEN=[%s]\n' "${GITHUB_TOKEN-<unset>}"
    for a in "$@"; do printf 'ARG=[%s]\n' "$a"; done
} | tee -a "$GHTS_TEST_LOG/gh.log"
exit "${FAKE_GH_RC:-0}"
FAKE

    # 失敗の型は2つ持つ。fail はトークンを stdout へ出したうえで非 0 で終わる
    # (rc を見ずに出力だけ見る実装と、失敗時の出力を漏らす実装を落とす)。
    # empty は rc 0 で何も出さない。
    cat >"$FAKE_DIR/security" <<'FAKE'
#!/bin/sh
set +x
printf '%s\n' "$*" >>"$GHTS_TEST_LOG/security.log"
account=""
while [ $# -gt 0 ]; do
    if [ "$1" = -a ]; then account=${2-}; fi
    shift
done
case "${FAKE_SECURITY_MODE:-ok}" in
fail)
    echo "tok-read-partial"
    exit 44
    ;;
empty) exit 0 ;;
esac
echo "tok-read-${account%:read}"
FAKE

    cat >"$FAKE_DIR/op" <<'FAKE'
#!/bin/sh
set +x
printf '%s\n' "$*" >>"$GHTS_TEST_LOG/op.log"
ref=""
for a in "$@"; do ref=$a; done
case "${FAKE_OP_MODE:-ok}" in
fail)
    printf 'tok-write-partial'
    exit 1
    ;;
empty) exit 0 ;;
esac
owner=${ref#op://*/gh-write-}
printf 'tok-write-%s' "${owner%/credential}"
FAKE

    # git は引数を残してから実物へ渡す。実物の場所は今ここで絶対パスに確定させる
    # (PATH で探すと偽物が自分自身を見つける)。
    local real_git
    real_git="$(command -v git)"
    cat >"$FAKE_DIR/git" <<FAKE
#!/bin/sh
set +x
printf '%s\\n' "\$*" >>"\$GHTS_TEST_LOG/git.log"
exec "$real_git" "\$@"
FAKE
    chmod +x "$FAKE_DIR/gh" "$FAKE_DIR/security" "$FAKE_DIR/op" "$FAKE_DIR/git"
}

# origin が acme のリポジトリを作る。hook から起動されたときに継承した GIT_DIR が
# 一時リポジトリではなく実リポジトリを指さないよう外す。
init_acme_repo() {
    env -u GIT_DIR -u GIT_WORK_TREE git init -q "$SHIM_REPO"
    env -u GIT_DIR -u GIT_WORK_TREE git -C "$SHIM_REPO" remote add origin https://github.com/acme/widgets.git
}

# shim を PATH 先頭に置いて /bin/bash (macOS では 3.2) から起動する。
# - 環境のトークン類は必ず外す。残っていると手順1に当たり、実トークンが偽の gh の
#   出力としてテストのログへ出る。
# - cwd は必ず明示する。bats の既定の cwd はこのリポジトリで、実物の origin を持つ。
# - CPU 時間を縛るのは、自分自身の再実行が無限再帰として現れるため。
# shim へ渡す環境は SHIM_ENV に、設定の場所は SHIM_CONF に入れてから呼ぶ。
# 127 で終わるはずの呼び出しは SHIM_RUN_OPTS=(-127) を入れてから呼ぶ (run が BW01 を出さない)。
run_shim() {
    local dir="$1"
    shift

    # 偽物が実物より前で解決されることを先に確かめる (すぐ後ろに実物の security がある)
    if [ "$(PATH="$FAKE_DIR:/usr/bin:/bin" command -v security)" != "$FAKE_DIR/security" ] ||
        [ "$(PATH="$FAKE_DIR:/usr/bin:/bin" command -v op)" != "$FAKE_DIR/op" ]; then
        echo "TEST_WIRING_BROKEN: fakes do not shadow the real binaries" >&2
        return 98
    fi

    local conf_env=()
    if [ -n "$SHIM_CONF" ]; then conf_env=("GH_TOKEN_SHIM_CONFIG=$SHIM_CONF"); fi

    run "${SHIM_RUN_OPTS[@]}" --separate-stderr env -u GH_TOKEN -u GITHUB_TOKEN -u GH_REPO -u GIT_DIR -u GIT_WORK_TREE \
        -u GH_TOKEN_SHIM_CONFIG -u SHELLOPTS \
        HOME="$SHIM_HOME" GHTS_TEST_SHIM_DIR="$SHIM_DIR" GHTS_TEST_LOG="$SHIM_LOG" \
        "${conf_env[@]}" "${SHIM_ENV[@]}" \
        /bin/bash -c '
            ulimit -t 10
            cd "$1" || exit 9
            PATH="$2"
            export PATH
            shift 2
            if [ "$(command -v gh)" != "$GHTS_TEST_SHIM_DIR/gh" ]; then
                echo "TEST_WIRING_BROKEN: gh does not resolve to the shim" >&2
                exit 98
            fi
            exec gh "$@"
        ' _ "$dir" "$SHIM_PATH" "$@"
}

# 偽物の記録 (無ければ空)
shim_log() {
    if [ -f "$SHIM_LOG/$1.log" ]; then cat "$SHIM_LOG/$1.log"; fi
}

# 偽物が一度も起動されていないこと。記録が効くことの陽性対照は、同じ偽物が起動される
# 別のテスト (exact な argv の検査) が持つ。
assert_not_called() {
    local name
    for name in "$@"; do
        if [ -s "$SHIM_LOG/$name.log" ]; then
            echo "$name は呼ばれないはずが呼ばれた: $(cat "$SHIM_LOG/$name.log")" >&2
            return 1
        fi
    done
}

# 本物が shim を経由して起動され、指定のトークンを受け取ったこと
assert_gh_ran_with_token() {
    refute_contains "$output" "BYPASSED_SHIM" || return 1
    assert_contains "$output" "REAL_GH_RAN" || return 1
    assert_contains "$output" "GH_TOKEN=[$1]"
}

# トークンの値がどこにも漏れていないこと (偽物が返す値は全て tok- で始まる)
refute_token_on_stderr() {
    refute_contains "$stderr" "tok-"
}

# 関数を引数つきで走らせ、rc が 0 で出力が期待と完全に一致することを確かめる
assert_exact_output() {
    local expected="$1"
    shift
    run "$@"
    if [ "$status" -ne 0 ] || [ "$output" != "$expected" ]; then
        echo "$*: rc 0 と [$expected] のはずが rc $status と [$output]" >&2
        return 1
    fi
}

# ghts_classify が引数を期待の分類にすること
assert_class() {
    local expected="$1"
    shift
    assert_exact_output "$expected" ghts_classify "$@"
}

# ghts_owner_from_args が引数から期待の持ち主を出すこと (空は「決められない」)
assert_owner() {
    local expected="$1"
    shift
    assert_exact_output "$expected" ghts_owner_from_args "$@"
}

# ghts_owner_from_url が URL から期待の持ち主を出すこと (空は「読めない」)
assert_url_owner() {
    assert_exact_output "$1" ghts_owner_from_url "$2"
}

# 偽物の記録が期待の1行と完全に一致すること
assert_shim_log() {
    local name="$1" expected="$2" actual
    actual="$(shim_log "$name")"
    if [ "$actual" != "$expected" ]; then
        echo "$name の記録は [$expected] のはずが [$actual]" >&2
        return 1
    fi
}

# op が指定の持ち主の強いトークンを1回だけ読んだこと。
# 期待する argv はここにだけ書く (本体から取ると、本体を変える変異が緑になる)
assert_op_read() {
    assert_shim_log op "read -n op://TestVault/gh-write-$1/credential"
}

# security が指定の持ち主の普段使いのトークンを1回だけ読んだこと
assert_security_read() {
    assert_shim_log security "find-generic-password -s gh-token-shim -a $1:read -w"
}

@test "classify: --version -> none" {
    assert_class none --version
}

@test "classify: version -> none" {
    assert_class none version
}

@test "classify: help -> none" {
    assert_class none help
}

@test "classify: help pr -> none" {
    assert_class none help pr
}

@test "classify: completion -s zsh -> none" {
    assert_class none completion -s zsh
}

@test "classify: auth status -> none" {
    assert_class none auth status
}

@test "classify: auth logout -> none" {
    assert_class none auth logout
}

@test "classify: (no args) -> none" {
    assert_class none
}

@test "classify: pr list -> read" {
    assert_class read pr list
}

@test "classify: pr view 3 -> read" {
    assert_class read pr view 3
}

@test "classify: pr create --fill -> read" {
    assert_class read pr create --fill
}

@test "classify: pr comment 3 --body-file x -> read" {
    assert_class read pr comment 3 --body-file x
}

@test "classify: issue create -> read" {
    assert_class read issue create
}

@test "classify: run view 1 -> read" {
    assert_class read run view 1
}

@test "classify: run watch 1 -> read" {
    assert_class read run watch 1
}

@test "classify: co 3 -> read" {
    assert_class read co 3
}

@test "classify: api repos/a/b -> read" {
    assert_class read api repos/a/b
}

@test "classify: api -X GET repos/a/b -> read" {
    assert_class read api -X GET repos/a/b
}

@test "classify: api --method=HEAD repos/a/b -> read" {
    assert_class read api --method=HEAD repos/a/b
}

@test "classify: api -X get repos/a/b -> read" {
    assert_class read api -X get repos/a/b
}

@test "classify: api --method=Head repos/a/b -> read" {
    assert_class read api --method=Head repos/a/b
}

@test "classify: api graphql -f query='query { viewer { login } }' -> read" {
    assert_class read api graphql -f query='query { viewer { login } }'
}

@test "classify: release view v1 -> read" {
    assert_class read release view v1
}

@test "classify: release list -> read" {
    assert_class read release list
}

@test "classify: repo view a/b -> read" {
    assert_class read repo view a/b
}

@test "classify: repo clone a/b -> read" {
    assert_class read repo clone a/b
}

@test "classify: ruleset list -> read" {
    assert_class read ruleset list
}

@test "classify: secret list -> read" {
    assert_class read secret list
}

@test "classify: pr merge 3 --squash -> write" {
    assert_class write pr merge 3 --squash
}

@test "classify: release create v1 -> write" {
    assert_class write release create v1
}

@test "classify: release upload v1 f -> write" {
    assert_class write release upload v1 f
}

@test "classify: release delete-asset v1 f -> write" {
    assert_class write release delete-asset v1 f
}

@test "classify: repo sync -> write" {
    assert_class write repo sync
}

@test "classify: workflow run ci.yml -> write" {
    assert_class write workflow run ci.yml
}

@test "classify: run rerun 1 -> write" {
    assert_class write run rerun 1
}

@test "classify: run cancel 1 -> write" {
    assert_class write run cancel 1
}

@test "classify: secret set X -> write" {
    assert_class write secret set X
}

@test "classify: variable delete X -> write" {
    assert_class write variable delete X
}

@test "classify: cache delete 1 -> write" {
    assert_class write cache delete 1
}

@test "classify: api -X POST repos/a/b/x -> write" {
    assert_class write api -X POST repos/a/b/x
}

@test "classify: api -XPOST repos/a/b/x -> write" {
    assert_class write api -XPOST repos/a/b/x
}

@test "classify: api --method=patch repos/a/b -> write" {
    assert_class write api --method=patch repos/a/b
}

@test "classify: api repos/a/b/labels -f name=x -> write" {
    assert_class write api repos/a/b/labels -f name=x
}

@test "classify: api repos/a/b -Fx=1 -> write" {
    assert_class write api repos/a/b -Fx=1
}

@test "classify: api repos/a/b --input body.json -> write" {
    assert_class write api repos/a/b --input body.json
}

@test "classify: api graphql -f query='mutation { x }' -> write" {
    assert_class write api graphql -f query='mutation { x }'
}

@test "classify: api graphql --input q.json -> write" {
    assert_class write api graphql --input q.json
}

@test "classify: api -X GET graphql --input q.json -> write" {
    # graphql は GET と書いても送る中身で決まる。メソッドだけで読み取りにしない
    assert_class write api -X GET graphql --input q.json
}

@test "classify: api -X GET graphql -f query='mutation { x }' -> write" {
    assert_class write api -X GET graphql -f 'query=mutation { x }'
}

@test "classify: api -X GET graphql -f query='{viewer{login}}' -> read" {
    assert_class read api -X GET graphql -f 'query={viewer{login}}'
}

@test "classify: api graphql -F query=@q.graphql -> write" {
    assert_class write api graphql -F query=@q.graphql
}

@test "classify: repo create a/b --private -> admin" {
    assert_class admin repo create a/b --private
}

@test "classify: repo delete a/b --yes -> admin" {
    assert_class admin repo delete a/b --yes
}

@test "classify: repo edit --visibility public -> admin" {
    assert_class admin repo edit --visibility public
}

@test "classify: repo rename x -> admin" {
    assert_class admin repo rename x
}

@test "classify: repo archive -> admin" {
    assert_class admin repo archive
}

@test "classify: repo unarchive -> admin" {
    assert_class admin repo unarchive
}

@test "classify: repo fork a/b -> admin" {
    assert_class admin repo fork a/b
}

@test "classify: repo deploy-key add k -> admin" {
    assert_class admin repo deploy-key add k
}

@test "classify: repo autolink create p u -> admin" {
    assert_class admin repo autolink create p u
}

@test "classify: repo deploy-key list -> read" {
    assert_class read repo deploy-key list
}

@test "classify: repo autolink view 1 -> read" {
    assert_class read repo autolink view 1
}

@test "classify: repo deploy-key delete 1 -> admin" {
    assert_class admin repo deploy-key delete 1
}

@test "classify: repo autolink delete 1 -> admin" {
    assert_class admin repo autolink delete 1
}

@test "classify: release delete v1 -> write" {
    assert_class write release delete v1
}

@test "classify: release edit v1 -> write" {
    assert_class write release edit v1
}

@test "classify: workflow enable x -> write" {
    assert_class write workflow enable x
}

@test "classify: workflow disable x -> write" {
    assert_class write workflow disable x
}

@test "classify: run delete 1 -> write" {
    assert_class write run delete 1
}

@test "classify: secret delete X -> write" {
    assert_class write secret delete X
}

@test "classify: secret remove X -> write" {
    assert_class write secret remove X
}

@test "classify: variable set X -> write" {
    assert_class write variable set X
}

@test "classify: variable remove X -> write" {
    assert_class write variable remove X
}

# --- none は先頭の語だけで決める ---
# gh は知らないフラグの次の語を値として読み飛ばしてからサブコマンドを決める。フラグの
# 後ろに version や help が見えても、それがサブコマンドとは限らない。none はトークンを
# 付けずに委譲する唯一の分類なので、取り違えると保存済みのログインで動く

@test "classify: --preview help api -X DELETE repos/acme/x -> read" {
    assert_class read --preview help api -X DELETE repos/acme/x
}

@test "classify: --squash version pr merge -> read" {
    assert_class read --squash version pr merge
}

@test "classify: -R bob/x version -> read" {
    assert_class read -R bob/x version
}

@test "classify: an empty first argument -> read" {
    assert_class read "" version
}

@test "classify: --help and -h alone -> none" {
    assert_class none --help
    assert_class none -h
}

@test "classify: --version followed by a command -> read" {
    assert_class read --version pr list
}

@test "classify: -h repo create x y -> read" {
    # 先頭の -h の後ろにコマンドが続く形を none にしない。none はトークン無しで
    # 委譲するので、gh がこの形をどう解釈しても、トークン無しで書き込みへ届く経路を作らない
    assert_class read -h repo create x y
}

@test "classify: --help pr merge 3 -> read" {
    assert_class read --help pr merge 3
}

# --- サブコマンドと動詞のあいだの -R / --repo とその値は、動詞に数えない ---

@test "classify: pr -R bob/x merge 3 -> write" {
    assert_class write pr -R bob/x merge 3
}

@test "classify: release -R acme/x create v1 -> write" {
    assert_class write release -R acme/x create v1
}

@test "classify: repo -R acme/x deploy-key add k -> admin" {
    assert_class admin repo -R acme/x deploy-key add k
}

# --- --help / -h: 何も実行しないので、書き込みと管理の判定を read へ下げる ---

@test "classify: pr merge --help -> read" {
    assert_class read pr merge --help
}

@test "classify: pr merge -h -> read" {
    assert_class read pr merge -h
}

@test "classify: release create --help -> read" {
    assert_class read release create --help
}

@test "classify: repo create --help -> read" {
    assert_class read repo create --help
}

@test "classify: pr merge 3 --body --help -> write" {
    # --help は --body の値で、gh は merge を実行する。none へ下げるとトークン無しで委譲する
    assert_class write pr merge 3 --body --help
}

@test "classify: repo create x -h URL -> admin" {
    # repo create の -h は --homepage で、値を取る
    assert_class admin repo create x -h https://example.com
}

@test "classify: api -X POST repos/a/b/x -H Accept:x -> write" {
    # gh api の -H はヘッダで、ヘルプではない
    assert_class write api -X POST repos/a/b/x -H Accept:x
}

@test "classify: api -X POST repos/a/b/x -h -> write" {
    assert_class write api -X POST repos/a/b/x -h
}

# --- query= の mutation は graphql のときだけ、語として見る ---

@test "classify: api -X GET repos/a/b/issues -f query=mutation -> read" {
    assert_class read api -X GET repos/acme/web/issues -f query=mutation
}

@test "classify: api -X GET repos/a/b -F query=@f -> read" {
    assert_class read api -X GET repos/a/b -F query=@f
}

@test "classify: api graphql -f query='{viewer{mutationCount}}' -> read" {
    assert_class read api graphql -f 'query={viewer{mutationCount}}'
}

@test "classify: api graphql with a mutation in each written form -> write" {
    assert_class write api graphql -f 'query=mutation{x}'
    assert_class write api graphql -f 'query=mutation($id:ID!){x(id:$id)}'
    assert_class write api graphql -f 'query=  Mutation Name { x }'
    assert_class write api graphql -f 'query=mutation'
}

@test "classify: api -f query='mutation { x }' graphql (field before the endpoint) -> write" {
    assert_class write api -f 'query=mutation { x }' graphql
}

# =============================================================================
# 持ち主の解決 (ghts_owner_from_args / ghts_owner_from_url) と設定の解釈
# =============================================================================

@test "owner_from_args: pr view 3 -R Acme/Web -> acme" {
    assert_owner acme pr view 3 -R Acme/Web
}

@test "owner_from_args: --repo=acme/web -> acme" {
    assert_owner acme pr view 3 --repo=acme/web
}

@test "owner_from_args: --repo acme/web (separate value) -> acme" {
    assert_owner acme pr view 3 --repo Acme/web
}

@test "owner_from_args: -R HOST/OWNER/REPO -> acme" {
    assert_owner acme pr view 3 -R github.com/acme/web
}

@test "owner_from_args: -R URL -> acme" {
    assert_owner acme pr view 3 -R https://github.com/acme/web
}

@test "owner_from_args: -R wins over api endpoint" {
    assert_owner acme api repos/other/web -R acme/web
}

@test "owner_from_args: api repos/Acme/web/rulesets -> acme" {
    assert_owner acme api repos/Acme/web/rulesets
}

@test "owner_from_args: api /repos/acme/web -> acme" {
    assert_owner acme api /repos/acme/web
}

@test "owner_from_args: api orgs/acme/members -> acme" {
    assert_owner acme api orgs/acme/members
}

@test "owner_from_args: api users/bob -> bob" {
    assert_owner bob api users/bob
}

@test "owner_from_args: api user -> empty" {
    assert_owner "" api user
}

@test "owner_from_args: api flags with values are not the endpoint" {
    assert_owner acme api -H "Accept: x" -X GET repos/acme/web
}

@test "owner_from_args: repo view acme/web -> acme" {
    assert_owner acme repo view acme/web
}

@test "owner_from_args: pr merge URL -> acme" {
    assert_owner acme pr merge https://github.com/acme/web/pull/3
}

@test "owner_from_args: pr list -> empty" {
    assert_owner "" pr list
}

@test "owner_from_args: search repos foo -> empty" {
    assert_owner "" search repos foo
}

@test "owner_from_args: pr create --base main --head feature/x -> empty" {
    assert_owner "" pr create --base main --head feature/x
}

@test "owner_from_args: pr checkout feature/x -> empty" {
    assert_owner "" pr checkout feature/x
}

@test "owner_from_args: pr merge 3 --body a/b -> empty" {
    assert_owner "" pr merge 3 --body a/b
}

@test "owner_from_args: release create v1 dist/x -> empty" {
    assert_owner "" release create v1 dist/x
}

@test "owner_from_args: workflow run .github/workflows/ci.yml -> empty" {
    assert_owner "" workflow run .github/workflows/ci.yml
}

@test "owner_from_args: issue create -t x/y -> empty" {
    assert_owner "" issue create -t x/y
}

@test "owner_from_url: scp style with .git" {
    assert_url_owner acme git@github.com:Acme/web.git
}

@test "owner_from_url: scp style without .git" {
    assert_url_owner acme git@github.com:acme/web
}

@test "owner_from_url: ssh scheme" {
    # リテラルの ssh://git@host/ は gitleaks の email-address に当たるので組み立てる
    local host=github.com
    assert_url_owner acme "ssh://git@${host}/acme/web"
}

@test "owner_from_url: https with .git" {
    assert_url_owner acme https://github.com/acme/web.git
}

@test "owner_from_url: https with trailing path" {
    assert_url_owner acme https://github.com/acme/web/pull/3
}

@test "owner_from_url: http scheme" {
    assert_url_owner acme http://github.com/Acme/web
}

@test "owner_from_url: www host" {
    assert_url_owner acme https://www.github.com/acme/web/pull/3
}

@test "owner_from_url: every ASCII uppercase letter is lowercased" {
    # 小文字化は1文字ずつの置換なので、26文字すべてを通す (1文字欠けても他の検査は緑)
    assert_url_owner abcdefghijklmnopqrstuvwxyz-0 https://GITHUB.COM/ABCDEFGHIJKLMNOPQRSTUVWXYZ-0/web
}

@test "owner_from_url: host that only starts with github.com -> empty" {
    assert_url_owner "" https://github.com.evil.test/acme/web
}

@test "owner_from_url: host that only ends with github.com -> empty" {
    assert_url_owner "" https://evilgithub.com/acme/web
}

@test "owner_from_url: api host is not a repository URL -> empty" {
    assert_url_owner "" https://api.github.com/repos/acme/web
}

@test "owner_from_args: -R http URL -> stranger" {
    assert_owner stranger pr merge 1 -R http://github.com/stranger/x
}

@test "owner_from_args: -R /x -> empty" {
    assert_owner "" pr merge 1 -R /x
}

@test "owner_from_args: api full URL on api.github.com -> owner" {
    assert_owner stranger api -X DELETE https://api.github.com/repos/Stranger/x/issues/1/labels
}

@test "owner_from_args: api full URL with an uppercase host -> owner" {
    assert_owner stranger api https://API.GitHub.com/repos/Stranger/x
}

@test "owner_from_args: api full URL on another host -> empty" {
    assert_owner "" api https://api.example.test/repos/acme/x
}

@test "owner_from_args: api full URL without an owner path -> empty" {
    assert_owner "" api https://api.github.com/user
}

# --- ghts_owner_source: どの解決元が「ある」か (値を読めるかどうかとは別) ---

@test "owner_source: -R -> args" {
    run ghts_owner_source pr view 3 -R acme/web
    [ "$output" = "args" ]
}

@test "owner_source: --repo= and -Rvalue -> args" {
    run ghts_owner_source pr view 3 --repo=acme/web
    [ "$output" = "args" ]
    run ghts_owner_source pr view 3 -Racme/web
    [ "$output" = "args" ]
}

@test "owner_source: -R with an unparseable or empty value is still args" {
    run ghts_owner_source pr merge 1 -R /x
    [ "$output" = "args" ]
    run ghts_owner_source pr merge 1 -R ""
    [ "$output" = "args" ]
}

@test "owner_source: api repos/ orgs/ users/ endpoints -> args" {
    run ghts_owner_source api repos/acme/web
    [ "$output" = "args" ]
    run ghts_owner_source api /orgs/acme/members
    [ "$output" = "args" ]
    run ghts_owner_source api -H "Accept: x" -X GET users/bob
    [ "$output" = "args" ]
}

@test "owner_source: api full URL on any host -> args" {
    run ghts_owner_source api https://api.github.com/repos/acme/web
    [ "$output" = "args" ]
    run ghts_owner_source api https://ghes.example.test/api/v3/user
    [ "$output" = "args" ]
}

@test "owner_source: api user and api graphql -> none" {
    run ghts_owner_source api user
    [ "$output" = "none" ]
    run ghts_owner_source api graphql -f 'query={viewer{login}}'
    [ "$output" = "none" ]
}

@test "owner_source: api endpoint with the {owner} placeholder is not args" {
    # gh がプレースホルダを現在のリポジトリ (GH_REPO / cwd) で埋めるので、
    # 名指しの無い呼び出しと同じに扱う
    run ghts_owner_source api 'repos/{owner}/{repo}/pulls'
    [ "$output" = "none" ]
    run ghts_owner_source api -X POST '/repos/{owner}/{repo}/labels' -f name=x
    [ "$output" = "none" ]
    GH_REPO=bob/x
    run ghts_owner_source api 'repos/{owner}/{repo}/pulls'
    [ "$output" = "gh_repo" ]
}

@test "owner_source: api endpoint with an explicit owner and the {repo} placeholder is args" {
    run ghts_owner_source api 'repos/acme/{repo}/pulls'
    [ "$output" = "args" ]
    assert_owner acme api 'repos/acme/{repo}/pulls'
}

@test "owner_source: api full URL with the {owner} placeholder stays args" {
    run ghts_owner_source api 'https://api.github.com/repos/{owner}/{repo}/pulls'
    [ "$output" = "args" ]
}

@test "owner_source: repo verb with a repository argument -> args" {
    run ghts_owner_source repo view acme/web
    [ "$output" = "args" ]
    # スラッシュが無くても「リポジトリを引数で指した」ことに変わりはない
    run ghts_owner_source repo sync myfork
    [ "$output" = "args" ]
}

@test "owner_source: repo verb without a repository argument -> none" {
    run ghts_owner_source repo sync
    [ "$output" = "none" ]
    # deploy-key / autolink の次の語は動詞でリポジトリではない
    run ghts_owner_source repo deploy-key list
    [ "$output" = "none" ]
    run ghts_owner_source repo autolink list
    [ "$output" = "none" ]
}

@test "owner_source: github.com URL positional -> args" {
    run ghts_owner_source pr merge https://github.com/acme/web/pull/3
    [ "$output" = "args" ]
}

@test "owner_source: other positionals and flag values -> none" {
    run ghts_owner_source pr merge 3 --body https://example.com/notes
    [ "$output" = "none" ]
    run ghts_owner_source pr merge 3 --body a/b
    [ "$output" = "none" ]
    run ghts_owner_source pr checkout feature/x
    [ "$output" = "none" ]
    run ghts_owner_source pr list
    [ "$output" = "none" ]
}

@test "owner_source: GH_REPO -> gh_repo, args win over it" {
    GH_REPO=bob/x
    run ghts_owner_source pr list
    [ "$output" = "gh_repo" ]
    run ghts_owner_source pr list -R acme/x
    [ "$output" = "args" ]
}

# --- フラグの値は位置引数に数えない ---

@test "owner_source: values of value-taking flags are not positionals" {
    run ghts_owner_source repo view --json nameWithOwner -q .nameWithOwner
    [ "$output" = "none" ]
    run ghts_owner_source repo sync -b main
    [ "$output" = "none" ]
    run ghts_owner_source repo sync --branch main
    [ "$output" = "none" ]
    run ghts_owner_source pr merge 3 --body https://github.com/bob/x/issues/1
    [ "$output" = "none" ]
    run ghts_owner_source pr comment 3 --body "https://github.com/bob/x/pull/1 see this"
    [ "$output" = "none" ]
    run ghts_owner_source pr create --title t --body https://github.com/stranger/x/issues/1
    [ "$output" = "none" ]
    run ghts_owner_source issue comment 3 -b https://github.com/stranger/x/issues/1
    [ "$output" = "none" ]
    run ghts_owner_source pr list -s https://github.com/bob/x
    [ "$output" = "none" ]
}

@test "owner_from_args: a positional after a flag value is still read" {
    assert_owner acme repo sync -b main acme/web
    assert_owner bob repo view --json name bob/x
    assert_owner acme pr view --json title https://github.com/acme/web/pull/3
}

@test "owner_from_args: --flag=value and attached short values do not skip the next word" {
    assert_owner acme repo sync --branch=main acme/web
    assert_owner acme repo sync -bmain acme/web
    assert_owner acme pr view --json=title https://github.com/acme/web/pull/3
}

@test "owner_from_args: a short flag that is a switch for the verb does not eat the URL" {
    # pr merge の -s は --squash、-d は --delete-branch。pr view の -w は --web
    assert_owner bob pr merge -s https://github.com/bob/x/pull/1
    assert_owner bob pr merge -d https://github.com/bob/x/pull/1
    assert_owner acme pr view -w https://github.com/acme/web/pull/3
    assert_owner acme repo view -w acme/web
}

# --- gh api のエンドポイントのクエリ文字列 ---

@test "owner_from_args: api 'orgs/acme?x=1' -> acme" {
    assert_owner acme api 'orgs/acme?x=1'
}

@test "owner_from_args: api 'repos/acme/x?per_page=1' -> acme" {
    assert_owner acme api 'repos/acme/x?per_page=1'
}

@test "owner_source: api 'orgs/{owner}?per_page=1' keeps the placeholder -> none" {
    run ghts_owner_source api 'orgs/{owner}?per_page=1'
    [ "$output" = "none" ]
}

# --- HOST/OWNER/REPO の HOST ---

@test "owner_from_args: -R with a host other than github.com -> empty" {
    assert_owner "" pr view 3 -R github.com.evil/acme/x
    assert_owner "" pr view 3 -R evil.example/acme/x
    assert_owner "" repo view github.com.evil/acme/x
    # 名指しはあるので、解決元は args のまま (後ろの解決元へ進ませない)
    run ghts_owner_source pr view 3 -R github.com.evil/acme/x
    [ "$output" = "args" ]
}

@test "owner_from_args: -R with the github.com host in other spellings -> acme" {
    assert_owner acme pr view 3 -R GitHub.com/Acme/x
    assert_owner acme pr view 3 -R www.github.com/acme/x
}

@test "owner_from_url: other host (gitlab scp) -> empty" {
    assert_url_owner "" git@gitlab.com:acme/web.git
}

@test "owner_from_url: GHES host -> empty" {
    assert_url_owner "" https://github.example.com/acme/web
}

@test "valid_owner: acme-1 accepted" {
    run ghts_valid_owner acme-1
    [ "$status" -eq 0 ]
}

@test "valid_owner: rejects bad names" {
    local bad
    for bad in -acme acme/x 'a;b' ../x '' "$(printf 'a%.0s' $(seq 1 40))"; do
        run ghts_valid_owner "$bad"
        [ "$status" -ne 0 ] || { echo "accepted: $bad"; return 1; }
    done
}

@test "valid_owner: 39 chars accepted" {
    run ghts_valid_owner "$(printf 'a%.0s' $(seq 1 39))"
    [ "$status" -eq 0 ]
}

@test "valid_owner: trailing newline rejected" {
    run ghts_valid_owner $'acme\n'
    [ "$status" -ne 0 ]
}

@test "valid_owner: embedded newline rejected" {
    run ghts_valid_owner $'acme\nx'
    [ "$status" -ne 0 ]
}

_write_config() {
    CONF="$BATS_TEST_TMPDIR/ghts.conf"
    printf '%s\n' "$@" >"$CONF"
}

@test "load_config: normal file sets three variables" {
    _write_config '# comment' '' 'vault=Dev Vault' 'default_owner=Acme' 'owner=Acme' '' 'owner=bob-2'
    ghts_load_config "$CONF"
    [ "$GHTS_VAULT" = "Dev Vault" ]
    [ "$GHTS_DEFAULT_OWNER" = "acme" ]
    [ "$GHTS_OWNERS" = "acme bob-2" ]
}

@test "load_config: missing vault -> rc 1" {
    _write_config 'default_owner=acme' 'owner=acme'
    run ghts_load_config "$CONF"
    [ "$status" -eq 1 ]
}

@test "load_config: missing default_owner -> rc 1" {
    _write_config 'vault=v' 'owner=acme'
    run ghts_load_config "$CONF"
    [ "$status" -eq 1 ]
}

@test "load_config: invalid owner line -> rc 1" {
    _write_config 'vault=v' 'default_owner=acme' 'owner=a;b'
    run ghts_load_config "$CONF"
    [ "$status" -eq 1 ]
}

@test "load_config: missing file -> rc 1" {
    run ghts_load_config "$BATS_TEST_TMPDIR/nonexistent.conf"
    [ "$status" -eq 1 ]
}

@test "load_config: last line without newline is read" {
    CONF="$BATS_TEST_TMPDIR/ghts.conf"
    printf 'vault=v\ndefault_owner=acme\nowner=zed' >"$CONF"
    ghts_load_config "$CONF"
    [ "$GHTS_OWNERS" = "zed acme" ]
}

@test "load_config: default_owner is an owner without its own owner line" {
    _write_config 'vault=v' 'default_owner=acme'
    ghts_load_config "$CONF"
    [ "$GHTS_OWNERS" = "acme" ]
    ghts_has_owner acme
}

@test "load_config: default_owner listed as owner too is not duplicated" {
    _write_config 'vault=v' 'default_owner=Acme' 'owner=bob' 'owner=acme'
    ghts_load_config "$CONF"
    [ "$GHTS_OWNERS" = "bob acme" ]
}

@test "load_config: file is never sourced" {
    local work="$BATS_TEST_TMPDIR/work"
    mkdir -p "$work"
    CONF="$work/ghts.conf"
    printf '%s\n' 'vault=$(touch pwned)' 'default_owner=acme' >"$CONF"
    cd "$work"
    ghts_load_config "$CONF"
    # 設定を実際に読んだ陽性対照: 値がリテラルのまま入る
    [ "$GHTS_VAULT" = '$(touch pwned)' ]
    [ ! -e "$work/pwned" ]
}

@test "has_owner: member and non-member" {
    GHTS_OWNERS="acme bob-2"
    ghts_has_owner acme
    ghts_has_owner bob-2
    run ghts_has_owner ac
    [ "$status" -ne 0 ]
    run ghts_has_owner ""
    [ "$status" -ne 0 ]
}

# =============================================================================
# 入口の shim (scripts/gh-token-shim/gh)
# =============================================================================

# --- 手順 1: 既存のトークンはそのまま通す ---

@test "shim: an existing GH_TOKEN passes through untouched, even for a write" {
    init_acme_repo
    SHIM_ENV=(GH_TOKEN=preset-token)

    run_shim "$SHIM_REPO" pr merge 3

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "preset-token"
    assert_contains "$output" "ARG=[merge]"
    assert_not_called security op git
}

@test "shim: an existing GITHUB_TOKEN alone also passes through, GH_TOKEN stays unset" {
    init_acme_repo
    SHIM_ENV=(GITHUB_TOKEN=preset-github)

    run_shim "$SHIM_REPO" pr list

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "<unset>"
    assert_contains "$output" "GITHUB_TOKEN=[preset-github]"
    assert_not_called security op git
}

@test "shim: an existing GH_TOKEN passes through before the config is read" {
    SHIM_CONF="$BATS_TEST_TMPDIR/missing.conf"
    SHIM_ENV=(GH_TOKEN=preset-token)

    run_shim "$SHIM_PLAIN" pr list -R acme/x

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "preset-token"
}

@test "shim: an empty GH_TOKEN counts as unset" {
    SHIM_ENV=(GH_TOKEN= GITHUB_TOKEN=)

    run_shim "$SHIM_PLAIN" pr list -R acme/x

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-acme"
}

# --- 手順 2: none はトークンなしで委譲する ---

@test "shim: --version is delegated without a config and without reading a token" {
    SHIM_CONF="$BATS_TEST_TMPDIR/missing.conf"

    run_shim "$SHIM_PLAIN" --version

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "<unset>"
    assert_contains "$output" "ARG=[--version]"
    assert_not_called security op git
}

@test "shim: no arguments at all is delegated" {
    # set -u の下で空の "$@" を展開できること (bash 3.2)
    run_shim "$SHIM_PLAIN"

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "<unset>"
    refute_contains "$output" "ARG="
    assert_not_called security op
}

@test "shim: a none-class word after a flag is not delegated without a token" {
    run_shim "$SHIM_PLAIN" --preview help api -X DELETE repos/acme/x

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-home"
    assert_security_read home
    assert_not_called op
}

# --- 手順 3: 設定 ---

@test "shim: without a config pr list stops and gh is not run" {
    SHIM_CONF="$BATS_TEST_TMPDIR/missing.conf"

    run_shim "$SHIM_PLAIN" pr list -R acme/x

    [ "$status" -eq 1 ]
    assert_contains "$stderr" "gh-token-shim: "
    assert_contains "$stderr" "$BATS_TEST_TMPDIR/missing.conf"
    assert_contains "$stderr" "$REPO_ROOT/scripts/gh-token-shim/config.example"
    [ -z "$output" ]
    assert_not_called gh security op
}

@test "shim: an invalid config stops the same way" {
    printf '%s\n' 'vault=TestVault' 'default_owner=home' 'owner=bad_name' >"$SHIM_CONF"

    run_shim "$SHIM_PLAIN" pr list -R acme/x

    [ "$status" -eq 1 ]
    assert_contains "$stderr" "config.example"
    assert_not_called gh security op
}

@test "shim: the config defaults to HOME/.config/gh-token-shim/config" {
    mkdir -p "$SHIM_HOME/.config/gh-token-shim"
    printf '%s\n' 'vault=HomeVault' 'default_owner=zed' 'owner=zed' \
        >"$SHIM_HOME/.config/gh-token-shim/config"
    SHIM_CONF=""

    run_shim "$SHIM_PLAIN" pr list

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-zed"
}

@test "shim: the config is read before the admin check" {
    SHIM_CONF="$BATS_TEST_TMPDIR/missing.conf"

    run_shim "$SHIM_PLAIN" repo create acme/x

    [ "$status" -eq 1 ]
    assert_contains "$stderr" "config.example"
    assert_not_called gh security op
}

# --- 手順 4: admin ---

@test "shim: repo create stops without reading any token" {
    run_shim "$SHIM_PLAIN" repo create acme/x

    [ "$status" -eq 1 ]
    assert_contains "$stderr" "gh-token-shim: "
    assert_contains "$stderr" "web UI"
    refute_contains "$stderr" "config.example"
    [ -z "$output" ]
    assert_not_called gh security op git
}

# --- 手順 5: 持ち主の解決 ---

@test "shim: pr list in a repo whose origin is acme uses the acme read token" {
    init_acme_repo

    run_shim "$SHIM_REPO" pr list

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-acme"
    assert_security_read acme
    [ "$(shim_log git)" = "remote get-url origin" ]
    assert_not_called op
    refute_token_on_stderr
}

@test "shim: -R wins over the origin of the cwd" {
    init_acme_repo

    run_shim "$SHIM_REPO" pr list -R bob/x

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-bob"
    # 引数で決まったら origin を見に行かない
    assert_not_called git
}

@test "shim: GH_REPO wins over the origin of the cwd" {
    init_acme_repo
    SHIM_ENV=(GH_REPO=bob/x)

    run_shim "$SHIM_REPO" pr list

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-bob"
    # GH_REPO で決まったら origin を見に行かない
    assert_not_called git
}

@test "shim: -R wins over GH_REPO" {
    SHIM_ENV=(GH_REPO=bob/x)

    run_shim "$SHIM_PLAIN" pr list -R acme/x

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-acme"
}

@test "shim: outside a repository the default owner is used" {
    run_shim "$SHIM_PLAIN" pr list

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-home"
    # git に聞いたうえで (失敗して) 既定へ落ちた
    [ "$(shim_log git)" = "remote get-url origin" ]
}

@test "shim: a read for an owner not in the config uses the default owner's read token" {
    init_acme_repo

    run_shim "$SHIM_REPO" pr view -R stranger/x

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-home"
    assert_security_read home
}

@test "shim: a read for an invalid owner name uses the default owner's read token" {
    run_shim "$SHIM_PLAIN" pr view -R 'ac_me/x'

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-home"
}

@test "shim: a write for an owner not in the config stops without calling op" {
    # cwd の origin は設定にある acme。-R の持ち主が設定に無いとき、後ろの解決元
    # (origin や既定の持ち主) へ進んで昇格してはいけない
    init_acme_repo

    run_shim "$SHIM_REPO" pr merge 1 -R stranger/x

    [ "$status" -eq 1 ]
    assert_contains "$stderr" "gh-token-shim: "
    assert_contains "$stderr" "stranger"
    [ -z "$output" ]
    assert_not_called gh security op
}

@test "shim: a write for an invalid owner name stops without calling op" {
    init_acme_repo

    run_shim "$SHIM_REPO" pr merge 1 -R 'ac_me/x'

    [ "$status" -eq 1 ]
    assert_contains "$stderr" "gh-token-shim: "
    # 検証を通らない名前は端末へそのまま出さない
    refute_contains "$stderr" "ac_me"
    assert_not_called gh security op
}

@test "shim: a write outside a repository uses the default owner even without an owner line" {
    printf '%s\n' 'vault=TestVault' 'default_owner=acme' >"$SHIM_CONF"

    run_shim "$SHIM_PLAIN" pr merge 1

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-write-acme"
    assert_op_read acme
}

# 解決元が「ある」のに持ち主を読めないとき、後ろの解決元へ進まない。
# どのテストも cwd の origin は設定にある acme で、進んでしまうと acme として昇格する。

@test "shim: a write with an unparseable -R stops instead of using the origin" {
    init_acme_repo

    run_shim "$SHIM_REPO" pr merge 1 -R /x

    [ "$status" -eq 1 ]
    assert_contains "$stderr" "gh-token-shim: "
    assert_not_called gh op security git
}

@test "shim: a write with -R as an http URL of an unlisted owner stops" {
    init_acme_repo

    run_shim "$SHIM_REPO" pr merge 1 -R http://github.com/stranger/x

    [ "$status" -eq 1 ]
    assert_contains "$stderr" "stranger"
    assert_not_called gh op security
}

@test "shim: a write with -R as a www URL of an unlisted owner stops" {
    init_acme_repo

    run_shim "$SHIM_REPO" pr merge 1 -R https://www.github.com/stranger/x

    [ "$status" -eq 1 ]
    assert_contains "$stderr" "stranger"
    assert_not_called gh op security
}

@test "shim: a write with GH_REPO as an http URL of an unlisted owner stops" {
    init_acme_repo
    SHIM_ENV=(GH_REPO=http://github.com/stranger/x)

    run_shim "$SHIM_REPO" pr merge 1

    [ "$status" -eq 1 ]
    assert_contains "$stderr" "stranger"
    assert_not_called gh op security
}

@test "shim: a write with GH_REPO naming an unlisted owner stops" {
    init_acme_repo
    SHIM_ENV=(GH_REPO=stranger/x)

    run_shim "$SHIM_REPO" pr merge 1

    [ "$status" -eq 1 ]
    assert_contains "$stderr" "stranger"
    assert_not_called gh op security
}

@test "shim: a write with an unparseable GH_REPO stops instead of using the origin" {
    init_acme_repo
    SHIM_ENV=(GH_REPO=/x)

    run_shim "$SHIM_REPO" pr merge 1

    [ "$status" -eq 1 ]
    assert_not_called gh op security git
}

@test "shim: an api write to a full URL of an unlisted owner stops" {
    init_acme_repo

    run_shim "$SHIM_REPO" api -X DELETE https://api.github.com/repos/stranger/x/issues/1/labels

    [ "$status" -eq 1 ]
    assert_contains "$stderr" "stranger"
    assert_not_called gh op security
}

@test "shim: an api write to a full URL on another host stops instead of using the origin" {
    init_acme_repo

    # パスは repos/acme/... の形。ホストを見ずに読むと設定にある acme として昇格する
    run_shim "$SHIM_REPO" api -X DELETE https://api.example.test/repos/acme/x/issues/1/labels

    [ "$status" -eq 1 ]
    assert_not_called gh op security git
}

@test "shim: a write whose origin is not a github.com URL stops instead of using the default owner" {
    env -u GIT_DIR -u GIT_WORK_TREE git init -q "$SHIM_REPO"
    env -u GIT_DIR -u GIT_WORK_TREE git -C "$SHIM_REPO" remote add origin https://gitlab.com/acme/w.git

    run_shim "$SHIM_REPO" pr merge 1

    [ "$status" -eq 1 ]
    # origin を実際に問い合わせたうえで止まった
    [ "$(shim_log git)" = "remote get-url origin" ]
    assert_not_called gh op security
}

@test "shim: a read with an unparseable -R uses the default owner, not the origin" {
    init_acme_repo

    run_shim "$SHIM_REPO" pr view -R /x

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-home"
}

@test "shim: a read whose origin is not a github.com URL uses the default owner" {
    env -u GIT_DIR -u GIT_WORK_TREE git init -q "$SHIM_REPO"
    env -u GIT_DIR -u GIT_WORK_TREE git -C "$SHIM_REPO" remote add origin https://gitlab.com/acme/w.git

    run_shim "$SHIM_REPO" pr list

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-home"
}

@test "shim: a write with -R as a www URL of a listed owner elevates for that owner" {
    run_shim "$SHIM_PLAIN" pr merge 1 -R https://www.github.com/bob/x

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-write-bob"
    assert_op_read bob
}

@test "shim: an api write to a full URL of a listed owner elevates for that owner" {
    init_acme_repo

    run_shim "$SHIM_REPO" api -X DELETE https://api.github.com/repos/bob/x/issues/1/labels

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-write-bob"
}

@test "shim: an api read with the {owner} placeholder uses the origin owner" {
    init_acme_repo

    run_shim "$SHIM_REPO" api 'repos/{owner}/{repo}/pulls'

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-acme"
    assert_contains "$output" "ARG=[repos/{owner}/{repo}/pulls]"
}

@test "shim: an api write with the {owner} placeholder elevates for the origin owner" {
    init_acme_repo

    run_shim "$SHIM_REPO" api -X POST 'repos/{owner}/{repo}/labels' -f name=x

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-write-acme"
    assert_op_read acme
}

@test "shim: an api write with the {owner} placeholder follows GH_REPO before the origin" {
    init_acme_repo
    SHIM_ENV=(GH_REPO=bob/x)

    run_shim "$SHIM_REPO" api -X POST 'repos/{owner}/{repo}/labels' -f name=x

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-write-bob"
}

# --- フラグの値を持ち主の名指しと取り違えない (どのテストも cwd の origin は acme) ---

@test "shim: repo view --json nameWithOwner -q .nameWithOwner uses the origin owner's read token" {
    init_acme_repo

    run_shim "$SHIM_REPO" repo view --json nameWithOwner -q .nameWithOwner

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-acme"
    assert_security_read acme
    assert_not_called op
}

@test "shim: repo sync -b main elevates for the origin owner" {
    init_acme_repo

    run_shim "$SHIM_REPO" repo sync -b main

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-write-acme"
    assert_op_read acme
}

@test "shim: repo sync --branch main elevates for the origin owner" {
    init_acme_repo

    run_shim "$SHIM_REPO" repo sync --branch main

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-write-acme"
    assert_op_read acme
}

@test "shim: pr merge with a github.com URL in --body asks op for the origin owner, not the URL's" {
    init_acme_repo

    run_shim "$SHIM_REPO" pr merge 3 --body https://github.com/bob/x/issues/1

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-write-acme"
    assert_op_read acme
    assert_not_called security
}

@test "shim: pr comment with a body that starts with a github.com URL uses the origin owner" {
    init_acme_repo

    run_shim "$SHIM_REPO" pr comment 3 --body "https://github.com/bob/x/pull/1 see this"

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-acme"
    assert_security_read acme
    assert_not_called op
}

@test "shim: pr create with an unlisted owner's URL in --body uses the origin owner" {
    init_acme_repo

    run_shim "$SHIM_REPO" pr create --title t --body "https://github.com/stranger/x/issues/1"

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-acme"
    assert_security_read acme
}

@test "shim: issue comment with an unlisted owner's URL in --body uses the origin owner" {
    init_acme_repo

    run_shim "$SHIM_REPO" issue comment 3 --body "https://github.com/stranger/x/issues/1"

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-acme"
    assert_security_read acme
}

@test "shim: pr merge -s URL elevates for the owner in the URL, not the origin" {
    # pr merge の -s は値を取らない (--squash)。次の語を値として読み飛ばすと、
    # 名指した bob ではなく origin の acme として昇格する
    init_acme_repo

    run_shim "$SHIM_REPO" pr merge -s https://github.com/bob/x/pull/1

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-write-bob"
    assert_op_read bob
    assert_not_called git
}

@test "shim: pr -R bob/x merge 3 elevates for bob even though -R comes before the verb" {
    # -R の値を動詞に数えると merge を見落とし、普段使いのトークンで本物へ渡す
    init_acme_repo

    run_shim "$SHIM_REPO" pr -R bob/x merge 3

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-write-bob"
    assert_op_read bob
    assert_not_called security git
}

@test "shim: pr merge -s 3 elevates for the origin owner" {
    init_acme_repo

    run_shim "$SHIM_REPO" pr merge -s 3

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-write-acme"
    assert_op_read acme
}

# --- --help は承認も拒否も起こさない ---

@test "shim: pr merge --help runs with the read token and never asks op" {
    init_acme_repo

    run_shim "$SHIM_REPO" pr merge --help

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-acme"
    assert_not_called op
}

@test "shim: repo create --help is not refused as an admin operation" {
    run_shim "$SHIM_PLAIN" repo create --help

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-home"
    assert_not_called op
}

# --- gh api の端の形 ---

@test "shim: an api GET with -f query=mutation on a REST endpoint never asks op" {
    run_shim "$SHIM_PLAIN" api -X GET repos/acme/web/issues -f query=mutation

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-acme"
    assert_not_called op
}

@test "shim: an api endpoint with a query string resolves the owner without it" {
    run_shim "$SHIM_PLAIN" api 'orgs/acme?x=1'

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-acme"
    assert_security_read acme
}

# --- HOST/OWNER/REPO の HOST が github.com でなければ読めない名指しとして扱う ---

@test "shim: a write with -R on a host that only starts with github.com stops" {
    init_acme_repo

    run_shim "$SHIM_REPO" pr merge 1 -R github.com.evil/acme/x

    [ "$status" -eq 1 ]
    assert_contains "$stderr" "gh-token-shim: "
    assert_not_called gh op security git
}

@test "shim: a write with GH_REPO on a host that only starts with github.com stops" {
    init_acme_repo
    SHIM_ENV=(GH_REPO=github.com.evil/acme/x)

    run_shim "$SHIM_REPO" pr merge 1

    [ "$status" -eq 1 ]
    assert_contains "$stderr" "gh-token-shim: "
    assert_not_called gh op security git
}

@test "shim: a read with -R on a host that only starts with github.com uses the default owner" {
    init_acme_repo

    run_shim "$SHIM_REPO" pr list -R github.com.evil/acme/x

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-home"
}

# --- 手順 6 / 7: トークンの読み出し ---

@test "shim: pr merge reads the acme write token from op and never touches security" {
    init_acme_repo

    run_shim "$SHIM_REPO" pr merge 3

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-write-acme"
    assert_op_read acme
    assert_not_called security
    refute_token_on_stderr
}

@test "shim: a write outside a repository uses the listed default owner" {
    run_shim "$SHIM_PLAIN" pr merge 3

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-write-home"
}

@test "shim: when op fails it stops and does not continue with the read token" {
    init_acme_repo
    SHIM_ENV=(FAKE_OP_MODE=fail)

    run_shim "$SHIM_REPO" pr merge 3

    [ "$status" -eq 1 ]
    assert_contains "$stderr" "gh-token-shim: "
    # op が実際に呼ばれて失敗した (止まった理由が手前の検査ではない)
    assert_op_read acme
    [ -z "$output" ]
    assert_not_called gh security
    refute_token_on_stderr
}

@test "shim: an empty answer from op counts as a failure" {
    init_acme_repo
    SHIM_ENV=(FAKE_OP_MODE=empty)

    run_shim "$SHIM_REPO" pr merge 3

    [ "$status" -eq 1 ]
    assert_op_read acme
    assert_not_called gh security
}

@test "shim: when security fails it stops and shows how to store the token" {
    init_acme_repo
    SHIM_ENV=(FAKE_SECURITY_MODE=fail)

    run_shim "$SHIM_REPO" pr list

    [ "$status" -eq 1 ]
    assert_contains "$stderr" "gh-token-shim: "
    assert_contains "$stderr" "security add-generic-password -s gh-token-shim -a acme:read -w"
    assert_security_read acme
    [ -z "$output" ]
    assert_not_called gh op
    refute_token_on_stderr
}

@test "shim: an empty answer from security counts as a failure" {
    init_acme_repo
    SHIM_ENV=(FAKE_SECURITY_MODE=empty)

    run_shim "$SHIM_REPO" pr list

    [ "$status" -eq 1 ]
    assert_contains "$stderr" "security add-generic-password -s gh-token-shim -a acme:read -w"
    assert_not_called gh op
}

@test "shim: the token is not traced even when xtrace is inherited" {
    # SHELLOPTS が export されていると shim の bash も xtrace で始まり、
    # GH_TOKEN=... exec の行がトークンごと stderr へ出る
    init_acme_repo
    SHIM_ENV=(SHELLOPTS=xtrace)

    run_shim "$SHIM_REPO" pr list

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-acme"
    # xtrace が実際に効いていた陽性対照
    assert_contains "$stderr" "+ set +x"
    refute_token_on_stderr
}

# --- 手順 8: 委譲 ---

@test "shim: arguments with spaces, quotes, globs and empty strings reach gh unchanged" {
    init_acme_repo

    run_shim "$SHIM_REPO" pr create --title "a b" --body "it's" --label '*' --milestone ''

    [ "$status" -eq 0 ]
    local expected
    expected="$(printf '%s\n' 'ARG=[pr]' 'ARG=[create]' 'ARG=[--title]' 'ARG=[a b]' \
        'ARG=[--body]' "ARG=[it's]" 'ARG=[--label]' 'ARG=[*]' 'ARG=[--milestone]' 'ARG=[]')"
    [ "$(shim_log gh | grep '^ARG=')" = "$expected" ]
    assert_gh_ran_with_token "tok-read-acme"
}

@test "shim: the exit code of the real gh is passed through" {
    SHIM_ENV=(FAKE_GH_RC=7)

    run_shim "$SHIM_PLAIN" pr list -R acme/x

    [ "$status" -eq 7 ]
    assert_gh_ran_with_token "tok-read-acme"
}

@test "shim: refuses to re-exec itself when another copy stays on PATH" {
    # 別名を PATH に残さないとこの分岐へ到達しない。-ef を外すと別名の shim が
    # 手順1 (GH_TOKEN あり) で素通しして本物まで届くので、rc と記録の両方で見る
    local alias_dir="$BATS_TEST_TMPDIR/shim-alias"
    mkdir -p "$alias_dir"
    ln -s "$SHIM_SOURCE" "$alias_dir/gh"
    ln -s "$LIB" "$alias_dir/lib.sh"
    SHIM_PATH="$SHIM_DIR:$alias_dir:$FAKE_DIR:/usr/bin:/bin"

    run_shim "$SHIM_PLAIN" pr list -R acme/x

    [ "$status" -eq 1 ]
    assert_contains "$stderr" "refusing to re-exec the shim itself"
    [ -z "$output" ]
    assert_not_called gh security
    refute_token_on_stderr
}

@test "shim: a write with a leftover shim copy on PATH stops before asking op" {
    # 本物へ委譲できないと分かっているのに承認ダイアログを出さない。
    # op が記録されることの陽性対照は "pr merge reads the acme write token" が持つ
    local alias_dir="$BATS_TEST_TMPDIR/shim-alias"
    mkdir -p "$alias_dir"
    ln -s "$SHIM_SOURCE" "$alias_dir/gh"
    ln -s "$LIB" "$alias_dir/lib.sh"
    SHIM_PATH="$SHIM_DIR:$alias_dir:$FAKE_DIR:/usr/bin:/bin"

    run_shim "$SHIM_PLAIN" pr merge 1 -R acme/x

    [ "$status" -eq 1 ]
    assert_contains "$stderr" "refusing to re-exec the shim itself"
    assert_not_called gh op security
}

@test "shim: a write with no real gh on PATH exits 127 before asking op" {
    # /usr/bin と /bin を PATH に入れない。shim はここまで外部コマンドを1つも要らない
    rm "$FAKE_DIR/gh"
    SHIM_PATH="$SHIM_DIR:$FAKE_DIR"

    SHIM_RUN_OPTS=(-127)
    run_shim "$SHIM_PLAIN" pr merge 1 -R acme/x

    [ "$status" -eq 127 ]
    assert_contains "$stderr" "gh-token-shim: "
    assert_not_called op security
}

@test "shim: exits 127 when no real gh is left on PATH" {
    # /usr/bin を PATH に入れない (CI の runner は /usr/bin/gh を持つ)。
    # shim はここまで外部コマンドを1つも要らない
    rm "$FAKE_DIR/gh"
    SHIM_PATH="$SHIM_DIR:$FAKE_DIR"

    SHIM_RUN_OPTS=(-127)
    run_shim "$SHIM_PLAIN" --version

    [ "$status" -eq 127 ]
    assert_contains "$stderr" "gh-token-shim: "
    [ -z "$output" ]
}

@test "shim: run as a bare file name from its own directory still finds lib.sh" {
    # bash gh の形では BASH_SOURCE にスラッシュが無い。PATH に shim は無いので、
    # run_shim の配線の検査は通さずに直接起動する
    run --separate-stderr env -u GH_TOKEN -u GITHUB_TOKEN -u GH_REPO -u GIT_DIR -u GIT_WORK_TREE \
        -u SHELLOPTS HOME="$SHIM_HOME" GHTS_TEST_SHIM_DIR="$SHIM_DIR" GHTS_TEST_LOG="$SHIM_LOG" \
        GH_TOKEN_SHIM_CONFIG="$SHIM_CONF" PATH="$FAKE_DIR:/usr/bin:/bin" \
        /bin/bash -c 'cd "$GHTS_TEST_SHIM_DIR" && exec /bin/bash gh pr list -R acme/x'

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-read-acme"
    assert_security_read acme
}

@test "shim: stops when lib.sh is missing instead of delegating without a token" {
    # 判定できないまま委譲すると gh は保存済みのログインで動き、承認の後ろに置いた
    # 書き込みが素通りする
    rm "$SHIM_DIR/lib.sh"

    run_shim "$SHIM_PLAIN" pr merge 1 -R acme/x

    [ "$status" -eq 1 ]
    assert_contains "$stderr" "gh-token-shim: "
    assert_not_called gh security op
}

# =============================================================================
# 取り付け (配布経路・PATH への差し込み・設定の雛形)
# =============================================================================

@test "wiring: is distributed by SYMLINK_PAIRS" {
    # 配布経路から落ちると shim が配置されず、本物の gh が保存済みのログインで直接動く
    load_pairs_array SYMLINK_PAIRS

    local pair found_shim=0 found_lib=0
    for pair in "${SYMLINK_PAIRS[@]}"; do
        case "$pair" in
        "scripts/gh-token-shim/gh|.local/libexec/gh-token-shim/gh") found_shim=1 ;;
        "scripts/gh-token-shim/lib.sh|.local/libexec/gh-token-shim/lib.sh") found_lib=1 ;;
        esac
    done

    [ "$found_shim" -eq 1 ]
    [ "$found_lib" -eq 1 ]
}

@test "wiring: the source is executable" {
    # 実行権限が落ちると PATH 解決から外れ、本物の gh が直接呼ばれて shim が素通りする
    [ -x "$SHIM_SOURCE" ]
}

@test "wiring: zshrc prepends the shim after mise activate" {
    # path 配列側へ書くと mise activate の再構成で本物より後ろへ落ちる。
    # 順序そのものが仕様なので行番号で pin する。
    local mise_line prepend_line
    mise_line="$(grep -n 'mise activate zsh' "$ZSHRC_FILE" | head -1 | cut -d: -f1)"
    prepend_line="$(grep -n 'libexec/gh-token-shim' "$ZSHRC_FILE" | head -1 | cut -d: -f1)"

    [ -n "$mise_line" ]
    [ -n "$prepend_line" ]
    [ "$prepend_line" -gt "$mise_line" ]
}

@test "wiring: the zshrc PATH entry matches the SYMLINK_PAIRS target" {
    # 配置先と PATH に入れる先が別々に書かれているので、片方だけ直すと shim は
    # 置かれるのに PATH に載らない (またはその逆) という無音の失敗になる
    load_pairs_array SYMLINK_PAIRS

    local pair target dir=""
    for pair in "${SYMLINK_PAIRS[@]}"; do
        case "$pair" in
        "scripts/gh-token-shim/gh|"*)
            target="${pair#*|}"
            dir="${target%/*}"
            ;;
        esac
    done

    [ -n "$dir" ]
    run grep -F "\$HOME/$dir" "$ZSHRC_FILE"
    [ "$status" -eq 0 ]
}

@test "wiring: config.example loads with ghts_load_config" {
    # 雛形が読めなくなると、利用者が写した設定がそのまま shim を止める
    ghts_load_config "$REPO_ROOT/scripts/gh-token-shim/config.example"
    [ "$GHTS_VAULT" = "Dev" ]
    [ "$GHTS_DEFAULT_OWNER" = "example-user" ]
    [ "$GHTS_OWNERS" = "example-org example-user" ]
}
