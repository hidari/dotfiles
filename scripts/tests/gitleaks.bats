#!/usr/bin/env bats
# =============================================================================
# .gitleaks.toml の custom ルール (macOS user-path 検出) と allowlist の検証
#
# 注意:
# - fixture の secret / user-path は printf のフォーマット引数で実行時に合成し、
#   このテストファイル自体にはスキャン対象のリテラルを残さない。
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
    [ -n "$SCAN_DIR" ] && rm -rf "$SCAN_DIR"
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

@test "passes clean content with no secret or user path" {
    printf 'greeting = "hello world"\nbase = "$HOME/Develop"\n' > "$SCAN_DIR/f.txt"
    scan
    [ "$status" -eq 0 ]
}
