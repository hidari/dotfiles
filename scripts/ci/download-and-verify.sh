#!/usr/bin/env bash
# =============================================================================
# CI のツール取得で共通する「HTTPS ダウンロード + 固定 sha256 検証」を1箇所へ集約する。
#
# setup-ast-grep / setup-neovim / gitleaks 導入ステップが独立に書いていた
#   curl (--proto '=https' 等の security flag 群) + sha256sum -c の2行
# を共通化し、検証手順を変えるときの drift を防ぐ。展開方法は3者で異なる
# (unzip / tar 全体 / tar 単一メンバ) ため展開は呼び出し側に残す。
#
# 使い方:
#   download-and-verify.sh <url> <sha256> <dest>
#     <url>    取得する HTTPS アーカイブの URL (tag 付け替えで中身が変わりうる mutable な参照)
#     <sha256> 期待する 64 桁 hex の sha256 (展開前に内容を pin する堰)
#     <dest>   保存先パス (この後、呼び出し側が展開する)
#
# テスト容易性のため verify_sha256 / download_and_verify を関数化し、
# source 時は main を走らせず関数だけ公開する (末尾の BASH_SOURCE guard)。
# set -euo pipefail は main の内側に置く。top-level に置くと source した
# テストシェルへ errexit が漏れるため (scripts/tests/download-and-verify.bats)。
# =============================================================================

# ダウンロード済みファイルの sha256 が期待値と一致するか検証する。
# 不一致・ファイル不在なら sha256sum が非0で返る。
verify_sha256() {
    local file="$1"
    local expected="$2"
    echo "${expected}  ${file}" | sha256sum -c -
}

# HTTPS 限定でアーカイブを取得し、固定 sha256 で内容を検証する。
download_and_verify() {
    local url="$1"
    local sha256="$2"
    local dest="$3"
    curl --proto '=https' --tlsv1.2 -fsSL -o "$dest" "$url"
    verify_sha256 "$dest" "$sha256"
}

main() {
    set -euo pipefail
    if [ "$#" -ne 3 ]; then
        echo "使い方: download-and-verify.sh <url> <sha256> <dest>" >&2
        return 2
    fi
    download_and_verify "$1" "$2" "$3"
}

# 直接実行時のみ main を走らせ、source 時は関数だけ公開する
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi
