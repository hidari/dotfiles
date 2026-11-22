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

    run --separate-stderr env -u GH_TOKEN -u GITHUB_TOKEN -u GH_REPO -u GIT_DIR -u GIT_WORK_TREE \
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

@test "classify: --version -> none" {
    run ghts_classify --version
    [ "$status" -eq 0 ]
    [ "$output" = "none" ]
}

@test "classify: version -> none" {
    run ghts_classify version
    [ "$status" -eq 0 ]
    [ "$output" = "none" ]
}

@test "classify: help -> none" {
    run ghts_classify help
    [ "$status" -eq 0 ]
    [ "$output" = "none" ]
}

@test "classify: help pr -> none" {
    run ghts_classify help pr
    [ "$status" -eq 0 ]
    [ "$output" = "none" ]
}

@test "classify: completion -s zsh -> none" {
    run ghts_classify completion -s zsh
    [ "$status" -eq 0 ]
    [ "$output" = "none" ]
}

@test "classify: auth status -> none" {
    run ghts_classify auth status
    [ "$status" -eq 0 ]
    [ "$output" = "none" ]
}

@test "classify: auth logout -> none" {
    run ghts_classify auth logout
    [ "$status" -eq 0 ]
    [ "$output" = "none" ]
}

@test "classify: (no args) -> none" {
    run ghts_classify
    [ "$status" -eq 0 ]
    [ "$output" = "none" ]
}

@test "classify: pr list -> read" {
    run ghts_classify pr list
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: pr view 3 -> read" {
    run ghts_classify pr view 3
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: pr create --fill -> read" {
    run ghts_classify pr create --fill
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: pr comment 3 --body-file x -> read" {
    run ghts_classify pr comment 3 --body-file x
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: issue create -> read" {
    run ghts_classify issue create
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: run view 1 -> read" {
    run ghts_classify run view 1
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: run watch 1 -> read" {
    run ghts_classify run watch 1
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: co 3 -> read" {
    run ghts_classify co 3
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: api repos/a/b -> read" {
    run ghts_classify api repos/a/b
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: api -X GET repos/a/b -> read" {
    run ghts_classify api -X GET repos/a/b
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: api --method=HEAD repos/a/b -> read" {
    run ghts_classify api --method=HEAD repos/a/b
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: api graphql -f query='query { viewer { login } }' -> read" {
    run ghts_classify api graphql -f query='query { viewer { login } }'
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: release view v1 -> read" {
    run ghts_classify release view v1
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: release list -> read" {
    run ghts_classify release list
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: repo view a/b -> read" {
    run ghts_classify repo view a/b
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: repo clone a/b -> read" {
    run ghts_classify repo clone a/b
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: ruleset list -> read" {
    run ghts_classify ruleset list
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: secret list -> read" {
    run ghts_classify secret list
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: pr merge 3 --squash -> write" {
    run ghts_classify pr merge 3 --squash
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: release create v1 -> write" {
    run ghts_classify release create v1
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: release upload v1 f -> write" {
    run ghts_classify release upload v1 f
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: release delete-asset v1 f -> write" {
    run ghts_classify release delete-asset v1 f
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: repo sync -> write" {
    run ghts_classify repo sync
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: workflow run ci.yml -> write" {
    run ghts_classify workflow run ci.yml
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: run rerun 1 -> write" {
    run ghts_classify run rerun 1
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: run cancel 1 -> write" {
    run ghts_classify run cancel 1
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: secret set X -> write" {
    run ghts_classify secret set X
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: variable delete X -> write" {
    run ghts_classify variable delete X
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: cache delete 1 -> write" {
    run ghts_classify cache delete 1
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: api -X POST repos/a/b/x -> write" {
    run ghts_classify api -X POST repos/a/b/x
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: api -XPOST repos/a/b/x -> write" {
    run ghts_classify api -XPOST repos/a/b/x
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: api --method=patch repos/a/b -> write" {
    run ghts_classify api --method=patch repos/a/b
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: api repos/a/b/labels -f name=x -> write" {
    run ghts_classify api repos/a/b/labels -f name=x
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: api repos/a/b -Fx=1 -> write" {
    run ghts_classify api repos/a/b -Fx=1
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: api repos/a/b --input body.json -> write" {
    run ghts_classify api repos/a/b --input body.json
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: api graphql -f query='mutation { x }' -> write" {
    run ghts_classify api graphql -f query='mutation { x }'
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: api graphql --input q.json -> write" {
    run ghts_classify api graphql --input q.json
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: api graphql -F query=@q.graphql -> write" {
    run ghts_classify api graphql -F query=@q.graphql
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: repo create a/b --private -> admin" {
    run ghts_classify repo create a/b --private
    [ "$status" -eq 0 ]
    [ "$output" = "admin" ]
}

@test "classify: repo delete a/b --yes -> admin" {
    run ghts_classify repo delete a/b --yes
    [ "$status" -eq 0 ]
    [ "$output" = "admin" ]
}

@test "classify: repo edit --visibility public -> admin" {
    run ghts_classify repo edit --visibility public
    [ "$status" -eq 0 ]
    [ "$output" = "admin" ]
}

@test "classify: repo rename x -> admin" {
    run ghts_classify repo rename x
    [ "$status" -eq 0 ]
    [ "$output" = "admin" ]
}

@test "classify: repo archive -> admin" {
    run ghts_classify repo archive
    [ "$status" -eq 0 ]
    [ "$output" = "admin" ]
}

@test "classify: repo unarchive -> admin" {
    run ghts_classify repo unarchive
    [ "$status" -eq 0 ]
    [ "$output" = "admin" ]
}

@test "classify: repo fork a/b -> admin" {
    run ghts_classify repo fork a/b
    [ "$status" -eq 0 ]
    [ "$output" = "admin" ]
}

@test "classify: repo deploy-key add k -> admin" {
    run ghts_classify repo deploy-key add k
    [ "$status" -eq 0 ]
    [ "$output" = "admin" ]
}

@test "classify: repo autolink create p u -> admin" {
    run ghts_classify repo autolink create p u
    [ "$status" -eq 0 ]
    [ "$output" = "admin" ]
}

@test "classify: repo deploy-key list -> read" {
    run ghts_classify repo deploy-key list
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: repo autolink view 1 -> read" {
    run ghts_classify repo autolink view 1
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: repo deploy-key delete 1 -> admin" {
    run ghts_classify repo deploy-key delete 1
    [ "$status" -eq 0 ]
    [ "$output" = "admin" ]
}

@test "classify: repo autolink delete 1 -> admin" {
    run ghts_classify repo autolink delete 1
    [ "$status" -eq 0 ]
    [ "$output" = "admin" ]
}

@test "classify: release delete v1 -> write" {
    run ghts_classify release delete v1
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: release edit v1 -> write" {
    run ghts_classify release edit v1
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: workflow enable x -> write" {
    run ghts_classify workflow enable x
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: workflow disable x -> write" {
    run ghts_classify workflow disable x
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: run delete 1 -> write" {
    run ghts_classify run delete 1
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: secret delete X -> write" {
    run ghts_classify secret delete X
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: secret remove X -> write" {
    run ghts_classify secret remove X
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: variable set X -> write" {
    run ghts_classify variable set X
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: variable remove X -> write" {
    run ghts_classify variable remove X
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

# =============================================================================
# 持ち主の解決 (ghts_owner_from_args / ghts_owner_from_url) と設定の解釈
# =============================================================================

@test "owner_from_args: pr view 3 -R Acme/Web -> acme" {
    run ghts_owner_from_args pr view 3 -R Acme/Web
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: --repo=acme/web -> acme" {
    run ghts_owner_from_args pr view 3 --repo=acme/web
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: --repo acme/web (separate value) -> acme" {
    run ghts_owner_from_args pr view 3 --repo Acme/web
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: -R HOST/OWNER/REPO -> acme" {
    run ghts_owner_from_args pr view 3 -R github.com/acme/web
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: -R URL -> acme" {
    run ghts_owner_from_args pr view 3 -R https://github.com/acme/web
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: -R wins over api endpoint" {
    run ghts_owner_from_args api repos/other/web -R acme/web
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: api repos/Acme/web/rulesets -> acme" {
    run ghts_owner_from_args api repos/Acme/web/rulesets
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: api /repos/acme/web -> acme" {
    run ghts_owner_from_args api /repos/acme/web
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: api orgs/acme/members -> acme" {
    run ghts_owner_from_args api orgs/acme/members
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: api users/bob -> bob" {
    run ghts_owner_from_args api users/bob
    [ "$status" -eq 0 ]
    [ "$output" = "bob" ]
}

@test "owner_from_args: api user -> empty" {
    run ghts_owner_from_args api user
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "owner_from_args: api flags with values are not the endpoint" {
    run ghts_owner_from_args api -H "Accept: x" -X GET repos/acme/web
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: repo view acme/web -> acme" {
    run ghts_owner_from_args repo view acme/web
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: pr merge URL -> acme" {
    run ghts_owner_from_args pr merge https://github.com/acme/web/pull/3
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: pr list -> empty" {
    run ghts_owner_from_args pr list
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "owner_from_args: search repos foo -> empty" {
    run ghts_owner_from_args search repos foo
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "owner_from_args: pr create --base main --head feature/x -> empty" {
    run ghts_owner_from_args pr create --base main --head feature/x
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "owner_from_args: pr checkout feature/x -> empty" {
    run ghts_owner_from_args pr checkout feature/x
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "owner_from_args: pr merge 3 --body a/b -> empty" {
    run ghts_owner_from_args pr merge 3 --body a/b
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "owner_from_args: release create v1 dist/x -> empty" {
    run ghts_owner_from_args release create v1 dist/x
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "owner_from_args: workflow run .github/workflows/ci.yml -> empty" {
    run ghts_owner_from_args workflow run .github/workflows/ci.yml
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "owner_from_args: issue create -t x/y -> empty" {
    run ghts_owner_from_args issue create -t x/y
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "owner_from_url: scp style with .git" {
    run ghts_owner_from_url git@github.com:Acme/web.git
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_url: scp style without .git" {
    run ghts_owner_from_url git@github.com:acme/web
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_url: ssh scheme" {
    # リテラルの ssh://git@host/ は gitleaks の email-address に当たるので組み立てる
    local host=github.com
    run ghts_owner_from_url "ssh://git@${host}/acme/web"
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_url: https with .git" {
    run ghts_owner_from_url https://github.com/acme/web.git
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_url: https with trailing path" {
    run ghts_owner_from_url https://github.com/acme/web/pull/3
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_url: other host (gitlab scp) -> empty" {
    run ghts_owner_from_url git@gitlab.com:acme/web.git
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "owner_from_url: GHES host -> empty" {
    run ghts_owner_from_url https://github.example.com/acme/web
    [ "$status" -eq 0 ]
    [ -z "$output" ]
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
    run ghts_valid_owner "$(printf 'acme\nx')"
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
    [ "$GHTS_OWNERS" = "zed" ]
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
    [ "$(shim_log security)" = "find-generic-password -s gh-token-shim -a acme:read -w" ]
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
    [ "$(shim_log security)" = "find-generic-password -s gh-token-shim -a home:read -w" ]
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

@test "shim: a write whose default owner is not listed stops without calling op" {
    printf '%s\n' 'vault=TestVault' 'default_owner=home' 'owner=acme' >"$SHIM_CONF"

    run_shim "$SHIM_PLAIN" pr merge 1

    [ "$status" -eq 1 ]
    assert_not_called gh security op
}

# --- 手順 6 / 7: トークンの読み出し ---

@test "shim: pr merge reads the acme write token from op and never touches security" {
    init_acme_repo

    run_shim "$SHIM_REPO" pr merge 3

    [ "$status" -eq 0 ]
    assert_gh_ran_with_token "tok-write-acme"
    [ "$(shim_log op)" = "read -n op://TestVault/gh-write-acme/credential" ]
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
    [ "$(shim_log op)" = "read -n op://TestVault/gh-write-acme/credential" ]
    [ -z "$output" ]
    assert_not_called gh security
    refute_token_on_stderr
}

@test "shim: an empty answer from op counts as a failure" {
    init_acme_repo
    SHIM_ENV=(FAKE_OP_MODE=empty)

    run_shim "$SHIM_REPO" pr merge 3

    [ "$status" -eq 1 ]
    [ "$(shim_log op)" = "read -n op://TestVault/gh-write-acme/credential" ]
    assert_not_called gh security
}

@test "shim: when security fails it stops and shows how to store the token" {
    init_acme_repo
    SHIM_ENV=(FAKE_SECURITY_MODE=fail)

    run_shim "$SHIM_REPO" pr list

    [ "$status" -eq 1 ]
    assert_contains "$stderr" "gh-token-shim: "
    assert_contains "$stderr" "security add-generic-password -s gh-token-shim -a acme:read -w"
    [ "$(shim_log security)" = "find-generic-password -s gh-token-shim -a acme:read -w" ]
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
    assert_not_called gh
    refute_token_on_stderr
}

@test "shim: exits 127 when no real gh is left on PATH" {
    # /usr/bin を PATH に入れない (CI の runner は /usr/bin/gh を持つ)。
    # shim 自身が要る外部コマンドだけを別のディレクトリへ並べる
    local sysbin="$BATS_TEST_TMPDIR/sysbin"
    mkdir -p "$sysbin"
    ln -s "$(command -v dirname)" "$sysbin/dirname"
    rm "$FAKE_DIR/gh"
    SHIM_PATH="$SHIM_DIR:$FAKE_DIR:$sysbin"

    run_shim "$SHIM_PLAIN" --version

    [ "$status" -eq 127 ]
    assert_contains "$stderr" "gh-token-shim: "
    [ -z "$output" ]
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
