#!/bin/bash

# Raycast Script Command のメタデータ
# @raycast.schemaVersion 1
# @raycast.title Neovim Cheatsheet
# @raycast.mode silent
# @raycast.packageName Cheatsheets
# @raycast.icon ⌨️
# @raycast.description Neovimチートシートを Quick Look で表示（Escで閉じる）

IMG="$HOME/.config/nvim/resources/nvim-cheatsheet.png"

# 古いプレビューが残っていれば閉じてから開き直す（残存プロセスに対する自己修復）
pkill -f "qlmanage -p .*nvim-cheatsheet" 2>/dev/null

# チートシートを Quick Look で表示（Esc / Space / クリックで閉じる）
qlmanage -p "$IMG" >/dev/null 2>&1 &

# バックグラウンド起動の qlmanage は前面に来ないため、ウィンドウ生成を待って前面化する。
# ウィンドウ生成には一瞬ラグがあるので、短い間隔で数回 frontmost を叩くレースガードにする。
# （初回のみ System Events 制御の Automation 権限ダイアログが出る）
(
    for _ in 1 2 3 4 5; do
        sleep 0.15
        osascript -e 'tell application "System Events" to set frontmost of (first process whose name is "qlmanage") to true' >/dev/null 2>&1
    done
) &

