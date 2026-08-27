#!/usr/bin/env bats
# =============================================================================
# .gitleaks.toml の custom ルール (macOS user-path / メールアドレス検出) と
# allowlist の検証
#
# 注意:
# - fixture の secret / user-path / メールアドレスは printf のフォーマット引数で
#   実行時に合成し、このテストファイル自体にはスキャン対象のリテラルを残さない。
#   (リテラルを書くと gitleaks 自身がこのファイルを leak として弾き、
#    public repo に username/secret が載る矛盾が起きるため)
# - bats はテスト名を関数名に変換するため @test 名は ASCII にする。
# - ルール/allowlist の検証用に gitleaks dir (ファイル走査) を使う。実際の
#   pre-commit / CI は gitleaks git (staged / commit 範囲) を使うが、
#   ルール評価ロジックは共通なので dir で検証して問題ない。
# =============================================================================

load test_helper

GITLEAKS_CONFIG="$REPO_ROOT/.gitleaks.toml"

setup() {
    command -v gitleaks >/dev/null 2>&1 || skip "gitleaks 未インストール"
    [ -f "$GITLEAKS_CONFIG" ] || skip ".gitleaks.toml が無い"
    SCAN_DIR=$(mktemp -d)
    REPORT="$SCAN_DIR/report.json"
}

teardown() {
    # skip 時は SCAN_DIR 未設定なので if 文で空を吸収する (&& 一行だと空時に exit 1 で teardown 失敗)
    if [ -n "${SCAN_DIR:-}" ]; then
        rm -rf "$SCAN_DIR"
    fi
}

# SCAN_DIR を repo の config で走査し JSON レポートを出力する (leak 検出時 exit!=0)
scan() {
    run gitleaks dir "$SCAN_DIR" -c "$GITLEAKS_CONFIG" --no-banner --redact \
        --report-format json --report-path "$REPORT"
}

# 指定した RuleID の finding がレポートに含まれるか
fired() {
    grep -Eq "\"RuleID\": *\"$1\"" "$REPORT" 2>/dev/null
}

@test "inherits default secret rules via extend useDefault" {
    # github PAT 形式を実行時合成 (ソースには ghp_ リテラルを残さない)
    printf 'gh_token = "ghp_%s"\n' "0123456789abcdefABCDEF0123456789wxyz" > "$SCAN_DIR/f.txt"
    scan
    [ "$status" -ne 0 ]
    # custom rule ではなく既定ルールが拾ったこと (= 継承が効いている証明)
    ! fired "macos-user-path"
}

@test "detects a real-username absolute path (custom rule)" {
    # 架空ユーザー名 alice で検証 (実ユーザー名はソースに残さない)
    printf 'p = "/Users/%s/Develop/foo"\n' "alice" > "$SCAN_DIR/f.txt"
    scan
    [ "$status" -ne 0 ]
    # たまたまではなく目的の custom rule が発火したことまで固定する
    fired "macos-user-path"
}

@test "allows /Users/example placeholder via allowlist" {
    printf 'p = "/Users/%s/Develop/foo"\n' "example" > "$SCAN_DIR/f.txt"
    scan
    [ "$status" -eq 0 ]
}

@test "allows /Users/runner CI path via allowlist" {
    printf 'p = "/Users/%s/work/repo"\n' "runner" > "$SCAN_DIR/f.txt"
    scan
    [ "$status" -eq 0 ]
}

@test "detects an email address (custom rule)" {
    # 架空のドメインで検証 (実アドレスはソースに残さない)。
    # ユーザー名パスと違い、メールは $HOME 形式へ書き換えても消えないので
    # 気づかないまま追跡下へ入りうる
    printf 'contact = "%s@%s"\n' "alice" "somewhere.test" > "$SCAN_DIR/f.txt"
    scan
    [ "$status" -ne 0 ]
    fired "email-address"
}

@test "allows example.com placeholder addresses via allowlist" {
    # ドキュメントの例示アドレスは追跡下に多数ある。塞ぐと編集のたびに赤くなる
    printf 'contact = "%s@%s"\n' "noreply" "example.com" > "$SCAN_DIR/f.txt"
    scan
    [ "$status" -eq 0 ]
}

@test "allows the git@ SSH URL user via allowlist" {
    # SSH URL の git@ は個人を指さない。フィクスチャで実際に使っている形
    printf 'url = "%s@%s:org/repo.git"\n' "git" "gitlab.com" > "$SCAN_DIR/f.txt"
    scan
    [ "$status" -eq 0 ]
}

# 以下 4 件は allowlist が許可語を終端させていなかったために素通りしていた形。
# 許可語で始まるだけの別名が丸ごと通る (境界に . を含めていたため) のと、
# git@ が SSH URL の形を確認せず任意ドメインを通していたのが原因。

@test "detects a username that merely starts with an allowlisted word" {
    printf 'p = "/Users/%s.%s/Develop/foo"\n' "user" "smith" > "$SCAN_DIR/f.txt"
    scan
    [ "$status" -ne 0 ]
    fired "macos-user-path"
}

@test "detects a username that merely starts with the example placeholder" {
    printf 'p = "/Users/%s.%s/Develop/foo"\n' "example" "co" > "$SCAN_DIR/f.txt"
    scan
    [ "$status" -ne 0 ]
    fired "macos-user-path"
}

@test "detects a username that merely starts with the shared placeholder" {
    printf 'p = "/Users/%s.%s/Develop/foo"\n' "shared" "acct" > "$SCAN_DIR/f.txt"
    scan
    [ "$status" -ne 0 ]
    fired "macos-user-path"
}

@test "detects a git@ address that is not an SSH clone URL" {
    # コロンとパスを伴わない git@ は clone URL ではなく、内部ホスト名を名指ししうる
    printf 'host = "%s@%s"\n' "git" "internal.corp.invalid" > "$SCAN_DIR/f.txt"
    scan
    [ "$status" -ne 0 ]
    fired "email-address"
}

@test "passes clean content with no secret or user path" {
    printf 'greeting = "hello world"\nbase = "$HOME/Develop"\n' > "$SCAN_DIR/f.txt"
    scan
    [ "$status" -eq 0 ]
}

# -----------------------------------------------------------------------------
# CI の range scan は commit 範囲を走査する。git log は既定で merge commit の diff を
# 出さないため、-m が無いと merge commit で初めて入った内容が gitleaks へ渡らない。
# 機構 (走査が merge を見ること) と取り付け (workflow が -m を渡すこと) を別々に pin する。
# -----------------------------------------------------------------------------

# 両親のどちらにも存在せず merge commit だけが持つ leak を含むリポジトリを作り、
# base commit の SHA を stdout へ返す。
make_evil_merge_repo() {
    local dir="$1" leak="$2"
    git init -q -b main "$dir"
    git -C "$dir" config user.email probe@example.com
    git -C "$dir" config user.name probe
    printf 'base\n' > "$dir/base.txt"
    git -C "$dir" add base.txt
    git -C "$dir" commit -qm base
    local base_sha
    base_sha=$(git -C "$dir" rev-parse HEAD)

    git -C "$dir" checkout -q -b feature
    printf 'feat\n' > "$dir/feat.txt"
    git -C "$dir" add feat.txt
    git -C "$dir" commit -qm feat

    git -C "$dir" checkout -q main
    printf 'mainside\n' > "$dir/mainside.txt"
    git -C "$dir" add mainside.txt
    git -C "$dir" commit -qm mainside

    # 競合しない併合にしてから、どちらの親にも無いファイルを merge commit へ載せる
    git -C "$dir" merge --no-ff --no-commit feature >/dev/null 2>&1 || true
    printf 'p = "%s"\n' "$leak" > "$dir/only-in-merge.txt"
    git -C "$dir" add only-in-merge.txt
    git -C "$dir" commit -qm merge

    printf '%s\n' "$base_sha"
}

# 指定した log-opts で範囲走査する (CI と同じ gitleaks git サブコマンド)
range_scan() {
    run gitleaks git "$1" --log-opts="$2" -c "$GITLEAKS_CONFIG" \
        --no-banner --redact --report-format json --report-path "$REPORT"
}

@test "the range scan sees a leak introduced only by a merge commit" {
    local repo base leak
    repo="$SCAN_DIR/repo"
    leak=$(printf '/Users/%s/Develop/foo' "alice")
    base=$(make_evil_merge_repo "$repo" "$leak")

    range_scan "$repo" "-m $base..HEAD"
    [ "$status" -ne 0 ]
    fired "macos-user-path"
}

@test "the range scan without -m misses that same leak" {
    # 上のテストが何を守っているかを示す対照。-m を落とすと同じ leak が見えなくなる。
    # この 2 件が揃って初めて「-m が効いている」と言える
    local repo base leak
    repo="$SCAN_DIR/repo"
    leak=$(printf '/Users/%s/Develop/foo' "alice")
    base=$(make_evil_merge_repo "$repo" "$leak")

    range_scan "$repo" "$base..HEAD"
    [ "$status" -eq 0 ]
}

@test "the range scan still catches a leak in an ordinary commit" {
    # -m を足したことで通常コミットの検出が壊れていないことの対照
    local repo base leak
    repo="$SCAN_DIR/repo"
    leak=$(printf '/Users/%s/Develop/foo' "alice")
    base=$(make_evil_merge_repo "$repo" "$leak")
    printf 'q = "%s"\n' "$(printf '/Users/%s/x' "bob")" > "$repo/ordinary.txt"
    git -C "$repo" add ordinary.txt
    git -C "$repo" commit -qm ordinary

    range_scan "$repo" "-m $base..HEAD"
    [ "$status" -ne 0 ]
    fired "macos-user-path"
}

@test "the CI leak guard is wired with -m" {
    # 機構が正しくても取り付けが外れれば何も守らない。workflow 側の配線を pin する
    run grep -qE 'gitleaks git --log-opts="-m ' "$REPO_ROOT/.github/workflows/test.yml"
    [ "$status" -eq 0 ]
}
