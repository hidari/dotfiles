#!/bin/bash

# @raycast.schemaVersion 1
# @raycast.title Herdr Cheatsheet
# @raycast.mode silent
# @raycast.packageName Cheatsheets
# @raycast.icon 🐑
# @raycast.description Herdr チートシートを Quick Look で表示（Escで閉じる）
IMG="$HOME/.config/herdr/resources/herdr-cheatsheet.png"

pkill -f "qlmanage -p .*herdr-cheatsheet" 2>/dev/null

qlmanage -p "$IMG" >/dev/null 2>&1 &

(
    for _ in 1 2 3 4 5; do
        sleep 0.15
        osascript -e 'tell application "System Events" to set frontmost of (first process whose name is "qlmanage") to true' >/dev/null 2>&1
    done
) &

