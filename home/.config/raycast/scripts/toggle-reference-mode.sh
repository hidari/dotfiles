#!/bin/bash

# Raycast Script Command
# @raycast.schemaVersion 1
# @raycast.title リファレンスモード切り替え
# @raycast.mode compact
#
# Optional parameters:
# @raycast.icon 🎯
# @raycast.packageName Display
# @raycast.description 内蔵ディスプレイのプリセットを編集用と普段用で切り替えます
# @raycast.author hidari

# 対象は内蔵ディスプレイのプリセット。ディスプレイペインで別のディスプレイが選択されて
# いる状態は想定していない。外部ディスプレイが Apple のリファレンス対応機
# (Pro Display XDR / Studio Display) だとプリセット名が下のリストと重なるため、
# その状態では意図しない側を切り替えうる。外部接続下での動作は未検証。

# プリセット popup を現在値で識別するためのリスト。System Settings の UI ツリーには
# AXIdentifier / AXHelp / AXTitle がいずれも無く (実測で 3 つの popup すべて
# missing value)、選択中の値で見分けるしかない。macOS 側でプリセット名が変われば
# ここも追随が要る。AppleScript へは引数で渡すので、この配列が唯一の定義になる。
PRESET_NAMES=(
    "Apple XDR Display (P3-1600 nits)"
    "Apple Display (P3-600 nits)"
    "HDR Video (P3-ST 2084)"
    "HDTV Video (BT.709-BT.1886)"
    "NTSC Video (BT.601 SMPTE-C)"
    "PAL & SECAM Video (BT.601 EBU)"
    "Digital Cinema (P3-DCI)"
    "Digital Cinema (P3-D65)"
    "Design & Print (P3-D50)"
    "Photography (P3-D65)"
    "Internet & Web (sRGB)"
)

# 切り替える 2 つのプリセット。どちらも PRESET_NAMES の要素でなければ popup を識別
# できず、タイムアウトしてから原因から遠いメッセージで落ちる。この対応は
# raycast-reference-mode.bats が pin する。
# 編集用は P3 系のリファレンスモード。リファレンス系のプリセットを選ぶと True Tone と
# 環境光による自動明るさ調整が無効になり、画面が既知の状態に固定される。
EDITING_PRESET="Photography (P3-D65)"
EVERYDAY_PRESET="Apple XDR Display (P3-1600 nits)"

# UI が現れるまで待つ上限 (秒)。System Settings のコールドスタートは実測で 1 秒では
# 足りず、quit 直後の再起動では 2 秒でも UI ツリーが空のことがある。固定待ちでは
# 保証できないので条件が満たされるまでポーリングし、この値は暴走を止める上限としてだけ使う。
# ペインが開いた後の UI ツリー走査は 1 回あたり実測 4〜5 秒かかるため、この上限は
# 走査 3〜4 回分に相当する。減らすときは走査コストと突き合わせること。
PRESET_WAIT_TIMEOUT=20

# AppleScript 本体。ヒアドキュメントを変数へ受けているのは、テストが source するだけで
# 本文を取り出せるようにするため。ファイルをマーカーで切り出す方式だと、マーカーが
# 動いて範囲が狭まったときに断片だけをコンパイルして緑のまま劣化する。
#
# `$(cat <<...)` ではなく read を使うのは、コマンド置換の中にヒアドキュメントを置くと
# 本文中の `AppleScript's` のアポストロフィを bash がクォートの開始と解釈して終端を
# 見失うため。read は EOF に達した時点で非ゼロを返すので || true で受ける
# (本文が空でないことは raycast-reference-mode.bats が pin する)。
#
# 引数は 4 つで固定する。
#   mode     read / apply / close
#   timeout  UI を待つ上限 (秒)
#   target   apply で切り替える先。read と close では空文字
#   presets  popup の識別に使う名前をタブ区切りで畳んだもの
IFS='' read -r -d '' DISPLAY_APPLESCRIPT <<'APPLESCRIPT' || true
-- popup の識別に使うプリセット名。canonical は呼び出し側 (bash) が持ち、
-- 引数で渡ってくる。ここは受け皿だけを用意する。
property presetNames : {}

on run argv
	set mode to item 1 of argv
	set timeoutSeconds to (item 2 of argv) as number
	set targetPreset to item 3 of argv
	set presetNames to my splitTabs(item 4 of argv)

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

-- タブ区切りの 1 引数をリストへ戻す。タブはプリセット名に現れない。
on splitTabs(s)
	set saved to AppleScript's text item delimiters
	set AppleScript's text item delimiters to tab
	set parts to text items of s
	set AppleScript's text item delimiters to saved
	return parts
end splitTabs

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
		set found to my locatePresetPopup()
		if found is not missing value then return found
		if (current date) > deadline then return missing value
	end repeat
end waitForPresetPopup

-- 走査の前提 (プロセスとウィンドウとペインの確定) をまとめて確かめてから探索へ入る。
-- System Settings はペインを選ぶまで window 名が空のままで、選ぶとペイン名が入る
-- (実測)。走査は下のコメントのとおり高コストなので、空の間は走査に入らず
-- 呼び出し側に reveal を送り直させる。名前そのものはロケール依存なので比較しない。
on locatePresetPopup()
	tell application "System Events"
		if not (exists application process "System Settings") then return missing value
		tell application process "System Settings"
			if (count of windows) is 0 then return missing value
			set wn to ""
			try
				set wn to (name of window 1) as text
			end try
			if wn is "" then return missing value
			return my searchPresetPopup(window 1)
		end tell
	end tell
end locatePresetPopup

-- プリセット popup を幅優先で探す。目的の popup は実測で深さ 6 にあり、深さ優先だと
-- 手前の枝を上限まで潜り切ってから戻るため無駄が大きい。同一条件で測った 1 回の走査:
--   深さ優先 + 要素ごとに role を取得   8 秒 (以前の実装)
--   深さ優先 + 1 階層まとめて role 取得 6〜7 秒
--   幅優先   + 1 階層まとめて role 取得 4〜5 秒
-- 深さ上限は暴走防止であって最適化ではない。上限を下げると macOS が階層を深くした
-- ときに「遅くなる」ではなく「見つからない」へ変わるので、幅優先化とは併用しない。
on searchPresetPopup(root)
	tell application "System Events"
		set frontier to {root}
		set depth to 0
		repeat while (count of frontier) > 0 and depth ≤ 14
			set nextFrontier to {}
			repeat with el in frontier
				set kids to {}
				try
					set kids to UI elements of el
				on error
					set kids to {}
				end try
				if (count of kids) > 0 then
					-- role は 1 階層まとめて取る。要素ごとに問い合わせると
					-- そのたびに Apple Event の往復が発生する。
					set roles to {}
					try
						set roles to role of UI elements of el
					on error
						set roles to {}
					end try
					if (count of roles) is (count of kids) then
						repeat with i from 1 to (count of kids)
							if (item i of roles) as text is "AXPopUpButton" then
								set v to ""
								try
									set v to ((value of item i of kids) as text)
								end try
								if presetNames contains v then return (contents of item i of kids)
							end if
							set end of nextFrontier to (contents of item i of kids)
						end repeat
					end if
				end if
			end repeat
			set frontier to nextFrontier
			set depth to depth + 1
		end repeat
	end tell
	return missing value
end searchPresetPopup

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

# PRESET_NAMES を AppleScript の 1 引数へ畳む。
preset_names_arg() {
    local IFS=$'\t'
    printf '%s' "${PRESET_NAMES[*]}"
}

run_display_script() {
    local mode="$1"
    local target="${2-}"

    printf '%s' "$DISPLAY_APPLESCRIPT" | osascript - "$mode" "$PRESET_WAIT_TIMEOUT" "$target" "$(preset_names_arg)"
}

read_current_preset() {
    run_display_script read
}

apply_preset() {
    run_display_script apply "$1"
}

# 失敗経路の後片付け。ここで失敗しても元のエラーを覆い隠さないよう握り潰す。
close_settings() {
    run_display_script close > /dev/null 2>&1 || true
}

# 現在のプリセットから次のプリセットを決める。編集用にいるときだけ普段用へ戻り、
# それ以外 (普段用・手動で選んだ第三のプリセット) からは編集用へ入る。
next_preset() {
    if [ "$1" = "$EDITING_PRESET" ]; then
        printf '%s' "$EVERYDAY_PRESET"
    else
        printf '%s' "$EDITING_PRESET"
    fi
}

# トグル本体。後片付けはここでは行わず main に集約する。失敗分岐ごとに close を
# 書く形にすると、分岐を足したときの書き忘れがそのまま「System Settings が
# 開きっぱなし」という元のバグの再発になる。
toggle_preset() {
    local current target applied

    # 空は UI 走査の失敗を意味する。「編集用ではない」と解釈して編集用へ倒すと、
    # 読み取れなかっただけなのに勝手にプリセットが変わる。
    if ! current=$(read_current_preset) || [ -z "$current" ]; then
        echo "現在のプリセットを読み取れませんでした" >&2
        return 1
    fi

    target=$(next_preset "$current")

    if ! applied=$(apply_preset "$target"); then
        echo "プリセットの適用に失敗しました" >&2
        return 1
    fi

    # click が成功しても実際には反映されないことがあるため、適用後の値を突き合わせる。
    if [ "$applied" != "$target" ]; then
        echo "プリセットが切り替わりませんでした (要求: $target / 実際: $applied)" >&2
        return 1
    fi

    printf '%s\n' "→ $target"
}

main() {
    if ! toggle_preset; then
        close_settings
        return 1
    fi
}

# source されたときは main を実行しない。テストが関数だけを読み込めるようにするため。
# set はここに置く。トップレベルに書くと source したシェルの挙動まで変えてしまう。
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    set -euo pipefail
    main "$@"
fi
