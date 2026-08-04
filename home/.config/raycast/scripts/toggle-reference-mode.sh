#!/bin/bash

# Raycast Script Command
# @raycast.schemaVersion 1
# @raycast.title リファレンスモード切り替え
# @raycast.mode compact
#
# Optional parameters:
# @raycast.icon 🎯
# @raycast.packageName Display
# @raycast.description 内蔵ディスプレイのプリセットを編集用 (Photography P3-D65) と普段用 (Apple XDR) で切り替えます
# @raycast.author hidari

# ===== 切り替える 2 つのプリセット =====
# 編集用は P3 系のリファレンスモード。リファレンス系のプリセットを選ぶと True Tone と
# 環境光による自動明るさ調整が無効になり、画面が既知の状態に固定される。
EDITING_PRESET="Photography (P3-D65)"
EVERYDAY_PRESET="Apple XDR Display (P3-1600 nits)"
# ======================================

# UI が現れるまで待つ上限 (秒)。System Settings のコールドスタートは実測で 1 秒では
# 足りず、quit 直後の再起動では 2 秒でも UI ツリーが空のことがある。固定待ちでは
# 保証できないので条件が満たされるまでポーリングし、この値は暴走を止める上限としてだけ使う。
# ペインが開いた後の UI ツリー走査は 1 回あたり実測 6 秒かかるため、この上限は
# 走査 2〜3 回分に相当する。減らすときは走査コストと突き合わせること。
PRESET_WAIT_TIMEOUT=20

# AppleScript 本体。mode / timeout / preset を引数で受け取り、3 つの役割を担う。
#   read   現在のプリセット名を返す (System Settings は開いたまま)
#   apply  指定プリセットへ切り替え、適用後の実際の値を返して System Settings を閉じる
#   close  System Settings を閉じるだけ (失敗経路の後片付け用)
run_display_script() {
    osascript - "$@" <<'APPLESCRIPT'
-- プリセット popup を現在値で識別するためのリスト。System Settings の UI ツリーには
-- AXIdentifier / AXHelp / AXTitle がいずれも無く (実測で 3 つの popup すべて
-- missing value)、選択中の値で見分けるしかない。macOS 側でプリセット名が変われば
-- ここも追随が要る。
property presetNames : {"Apple XDR Display (P3-1600 nits)", "Apple Display (P3-600 nits)", "HDR Video (P3-ST 2084)", "HDTV Video (BT.709-BT.1886)", "NTSC Video (BT.601 SMPTE-C)", "PAL & SECAM Video (BT.601 EBU)", "Digital Cinema (P3-DCI)", "Digital Cinema (P3-D65)", "Design & Print (P3-D50)", "Photography (P3-D65)", "Internet & Web (sRGB)"}

on run argv
	set mode to item 1 of argv
	set timeoutSeconds to (item 2 of argv) as number
	set targetPreset to ""
	if (count of argv) > 2 then set targetPreset to (item 3 of argv)

	if mode is "close" then
		my closeSettings()
		return ""
	end if

	set presetPopup to my waitForPresetPopup(timeoutSeconds)
	if presetPopup is missing value then
		error "プリセットのコントロールが見つかりませんでした"
	end if

	if mode is "read" then
		return my popupValue(presetPopup)
	else if mode is "apply" then
		my selectPreset(presetPopup, targetPreset, timeoutSeconds)
		set applied to my popupValue(presetPopup)
		my closeSettings()
		return applied
	end if

	error "未知の mode: " & mode
end run

-- ディスプレイペインを開く。reveal はコールドスタートで「エラーを返さないまま
-- 無視される」ことがあり、成否を戻り値からは判定できない。到達したかどうかは
-- 呼び出し側が UI ツリーを見て判断し、届いていなければ送り直す。
on openDisplaysPane()
	tell application "System Settings"
		activate
		try
			reveal pane id "com.apple.Displays-Settings.extension"
		end try
	end tell
end openDisplaysPane

on closeSettings()
	try
		tell application "System Settings" to quit
	end try
end closeSettings

on popupValue(popupElement)
	tell application "System Events"
		return ((value of popupElement) as text)
	end tell
end popupValue

-- System Settings を確実に前面へ出す。
-- `tell application "System Settings" to activate` だけでは足りない。実測の対照:
--   activate 1 回のみ    40 秒待って popup 0。frontmost は他アプリのまま
--   activate を毎周回     25 秒待って popup 0 (reveal は初回のみ)。frontmost には
--                        なるが window 名は空
--   下の set frontmost    1 周目 (0.6 秒) で popup 3、window 名は「ディスプレイ」
-- System Settings は SwiftUI 製で、前面に出るまでウィンドウの中身を描画しない。
-- 一度描画されれば背面でも UI ツリーは残るため、ウォームスタートでは activate だけでも
-- 動いてしまう。ただし前面化はコールドスタート失敗の一層でしかなく、前面に出ていても
-- ペイン遷移そのものが届かない層が別にある (waitForPresetPopup のコメントを参照)。
on bringSettingsToFront()
	tell application "System Events"
		try
			tell application process "System Settings" to set frontmost to true
		end try
	end tell
end bringSettingsToFront

-- プリセット popup が UI ツリーに現れるまで待つ。ペインの描画完了を表す信号は
-- 他に無いので、探しているもの自体が現れたかを条件にする。
--
-- ペインを開く操作を毎周回送り直すのは、コールドスタートで reveal が黙って
-- 捨てられるため。実測の対照 (内蔵ディスプレイのみ、コールドスタート):
--   reveal 1 回のみ   12 周 6 秒観測しても window 名は空のまま popup 0。
--                     その状態で reveal を送り直すと 0.5 秒後に popup 1
--   reveal 毎周回     1 周目で window 名「ディスプレイ」と popup 1 に到達
-- activate はアプリの起動完了を待ってブロックするが、その完了判定は Apple Event で
-- ペインを切り替えられる状態より早く返ることがある。何秒待てば足りるかは実行ごとに
-- 揺れるので、待ち時間を伸ばすのではなく送り直しで吸収する。
on waitForPresetPopup(timeoutSeconds)
	set deadline to (current date) + timeoutSeconds
	repeat
		my openDisplaysPane()
		my bringSettingsToFront()
		delay 0.5
		-- ペインが選ばれるまで UI ツリーの走査には入らない。走査は AX API への
		-- 問い合わせを要素ごとに繰り返すため 1 回あたり実測 6 秒かかり、ペインが
		-- 空のまま回すとタイムアウトの持ち分を走査だけで使い切ってしまう。
		-- 空の間は 0.5 秒周期で reveal を送り直すほうが、同じ制限時間で試行回数を稼げる。
		if my settingsPaneIsOpen() then
			set found to my findPresetPopupInAllWindows()
			if found is not missing value then return found
		end if
		if (current date) > deadline then return missing value
	end repeat
end waitForPresetPopup

-- ペインが選ばれた状態かどうかを window 名で判定する。System Settings は
-- ペインを選ぶまで window 名が空のままで、選ぶとペイン名が入る (実測)。
-- 名前そのものはロケール依存なので、特定の文字列とは比較しない。
on settingsPaneIsOpen()
	tell application "System Events"
		if not (exists application process "System Settings") then return false
		tell application process "System Settings"
			if (count of windows) is 0 then return false
			set wn to ""
			try
				set wn to (name of window 1) as text
			end try
			return wn is not ""
		end tell
	end tell
end settingsPaneIsOpen

on findPresetPopupInAllWindows()
	tell application "System Events"
		if not (exists application process "System Settings") then return missing value
		tell application process "System Settings"
			repeat with i from 1 to (count of windows)
				set tp to my findPresetPopup(window i, 0)
				if tp is not missing value then return tp
			end repeat
		end tell
	end tell
	return missing value
end findPresetPopupInAllWindows

-- 子要素を再帰的にたどってプリセット用 popup を探す。深さ上限は暴走防止。
-- 実測では目的の popup は深さ 6 にある。
on findPresetPopup(el, depth)
	if depth > 14 then return missing value
	tell application "System Events"
		set kids to {}
		try
			set kids to UI elements of el
		on error
			return missing value
		end try
		repeat with k in kids
			try
				if ((role of k) as text) is "AXPopUpButton" then
					set v to ""
					try
						set v to ((value of k) as text)
					end try
					if presetNames contains v then return (contents of k)
				end if
			end try
			try
				set sub to my findPresetPopup(k, depth + 1)
				if sub is not missing value then return sub
			end try
		end repeat
		return missing value
	end tell
end findPresetPopup

-- メニューを開いて指定プリセットを選び、値が実際に変わるまで待つ。
on selectPreset(popupElement, targetPreset, timeoutSeconds)
	tell application "System Events"
		tell application process "System Settings"
			click popupElement

			set menuDeadline to (current date) + timeoutSeconds
			repeat until (count of menus of popupElement) > 0
				if (current date) > menuDeadline then
					error "プリセットのメニューが開きませんでした"
				end if
				delay 0.1
			end repeat

			click menu item targetPreset of menu 1 of popupElement

			-- 切り替えにはディスプレイの再構成が挟まるため、click の直後には値が
			-- 変わっていないことがある。上限まで待ち、届かなければ呼び出し側が
			-- 適用後の値との突き合わせで失敗を検出する。
			set applyDeadline to (current date) + timeoutSeconds
			repeat until ((value of popupElement) as text) is targetPreset
				if (current date) > applyDeadline then exit repeat
				delay 0.2
			end repeat
		end tell
	end tell
end selectPreset
APPLESCRIPT
}

read_current_preset() {
    run_display_script read "$PRESET_WAIT_TIMEOUT"
}

apply_preset() {
    run_display_script apply "$PRESET_WAIT_TIMEOUT" "$1"
}

# 失敗経路の後片付け。ここで失敗しても元のエラーを覆い隠さないよう握り潰す。
close_settings() {
    run_display_script close "$PRESET_WAIT_TIMEOUT" >/dev/null 2>&1 || true
}

# 現在のプリセットから次のプリセットを決める。編集用にいるときだけ普段用へ戻り、
# それ以外 (普段用・手動で選んだ第三のプリセット) からは編集用へ入る。
next_preset() {
    local current="$1"

    # 空は UI 走査の失敗を意味する。「編集用ではない」と解釈して編集用へ倒すと、
    # 読み取れなかっただけなのに勝手にプリセットが変わる。
    if [ -z "$current" ]; then
        echo "現在のプリセットを読み取れませんでした" >&2
        return 1
    fi

    if [ "$current" = "$EDITING_PRESET" ]; then
        printf '%s' "$EVERYDAY_PRESET"
    else
        printf '%s' "$EDITING_PRESET"
    fi
}

main() {
    local current target applied

    if ! current=$(read_current_preset); then
        close_settings
        echo "ディスプレイ設定を読み取れませんでした" >&2
        return 1
    fi

    if ! target=$(next_preset "$current"); then
        close_settings
        return 1
    fi

    if ! applied=$(apply_preset "$target"); then
        close_settings
        echo "プリセットの適用に失敗しました" >&2
        return 1
    fi

    # click が成功しても実際には反映されないことがあるため、適用後の値を突き合わせる。
    if [ "$applied" != "$target" ]; then
        close_settings
        echo "プリセットが切り替わりませんでした (要求: $target / 実際: $applied)" >&2
        return 1
    fi

    printf '%s\n' "→ $target"
}

# source されたときは main を実行しない。テストが関数だけを読み込めるようにするため。
# set はここに置く。トップレベルに書くと source したシェルの挙動まで変えてしまう。
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    set -euo pipefail
    main "$@"
fi
