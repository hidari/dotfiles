#!/usr/bin/env bats
# =============================================================================
# scripts/ci/download-and-verify.sh の sha256 検証ロジックの単体テスト
#
# curl の HTTPS ダウンロードは実ネットワーク依存のためここでは検証しない
# (CI での実アーカイブ取得が live smoke になる)。供給網の堰である固定 sha256 の
# 照合が「一致で通り、不一致・ファイル不在で確実に落ちる」ことをオフラインで pin する。
#
# 注意:
# - @test 名は ASCII にする (bats はテスト名を関数名へエンコードするため。
#   rules/bats-test-name-ascii-only.yml)。説明は本文コメントで日本語可。
# - 裸の [[ ]] は使わず単一 [ ] で書く (rules/bats-no-bare-double-bracket.yml)。
# - 検証関数は source で取り込む。スクリプトは BASH_SOURCE guard により source 時は
#   main を走らせないため、取り込んでも副作用が無い。
# =============================================================================

load test_helper

DOWNLOAD_VERIFY_SCRIPT="$REPO_ROOT/scripts/ci/download-and-verify.sh"

# 実ファイルの sha256 と衝突しない不一致 digest (64 桁のゼロ)
WRONG_SHA256="0000000000000000000000000000000000000000000000000000000000000000"

setup() {
    command -v sha256sum >/dev/null 2>&1 || skip "sha256sum 未インストール"
    # 関数だけ公開される (source 時は main を走らせない BASH_SOURCE guard)
    source "$DOWNLOAD_VERIFY_SCRIPT"
    FIXTURE=$(mktemp)
    printf 'dotfiles-download-verify-fixture' > "$FIXTURE"
    EXPECTED_SHA256=$(sha256sum "$FIXTURE" | cut -d' ' -f1)
}

teardown() {
    if [ -n "${FIXTURE:-}" ]; then
        rm -f "$FIXTURE"
    fi
}

@test "verify_sha256 accepts a digest that matches the file" {
    run verify_sha256 "$FIXTURE" "$EXPECTED_SHA256"
    [ "$status" -eq 0 ]
}

@test "verify_sha256 rejects a digest that does not match the file" {
    run verify_sha256 "$FIXTURE" "$WRONG_SHA256"
    [ "$status" -ne 0 ]
}

@test "verify_sha256 rejects when the target file is missing" {
    run verify_sha256 "$FIXTURE.does-not-exist" "$EXPECTED_SHA256"
    [ "$status" -ne 0 ]
}
