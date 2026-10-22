#!/usr/bin/env bash
# =============================================================================
# 禁止語リストの層 (漏洩検査の層 2) を追跡ファイルのパスと内容へ当てる pre-commit の入口。
#
# 照合の仕様は checker (apm の deploy 先) の docstring が canonical。ここが持つのは、
# リストの在り処を指す LEAK_GUARD_DENYLIST が届かない起動元で止める (fail-closed) ことだけ。
# checker は未設定を rc 0 の skip にし、pre-commit は rc 0 の hook の出力を表示しないので、
# .zshenv を読まない起動元 (GUI の git クライアントや IDE の VCS 機能) からのコミットが
# 黙って素通りする。このリポジトリは PUBLIC で、露出は事後に取り消せないので止める側に倒す。
# リストを持たないマシンでは SKIP=leak-guard-denylist を明示して抜ける。
#
# 空の値は未設定と同じに扱わない。空は checker が rc 2 で拒む別の枝なので、そのまま渡す。
# =============================================================================
set -euo pipefail

if [ -z "${LEAK_GUARD_DENYLIST+set}" ]; then
    echo "禁止語ガード: LEAK_GUARD_DENYLIST が届いていないので止めた (この起動元は .zshenv を読んでいない)。リストを持たないマシンでは SKIP=leak-guard-denylist を付けてコミットする" >&2
    exit 2
fi

# checker は deploy 先に在り fresh clone には無い。無いときは python3 が rc 2 で落ちるので
# 検査が無音で消える形にはならない
root="$(git rev-parse --show-toplevel)"
exec python3 "$root/home/.claude/skills/dev-workflow/skills/commit-and-pr-message/scripts/check-leak-guard-denylist.py" --check
