#!/usr/bin/env python3
# herdr キーバインドのチートシート SVG を生成する source スクリプト。
#
# これがチートシート SVG（レイアウト・配色）の生成 source。バインドの内容は
# config.toml から手で curate しており、bind 自体の真実源は config.toml 側。
# バインドや配色を変えるときはこのスクリプトを編集し、次で成果物を再生成する:
#   python3 herdr-cheatsheet.py   # herdr-cheatsheet.svg を再出力
#   # PNG は SVG を headless ブラウザでラスタライズして更新する。
#   # 出力サイズは SVG root の width/height に合わせる（高さは内容で変わる）。
#
# レイアウトは nvim-cheatsheet.svg のカード構造・メトリクスを踏襲し、パレットのみ
# Catppuccin Mocha へ差し替えて nvim シートと一目で区別できるようにしている。
import html
import os

# --- Catppuccin Mocha パレット（nvim の One Dark ロールに対応づけ） ---
PAGE_BG = "#1e1e2e"    # base    （nvim: #282c34）
CARD_BG = "#181825"    # mantle  （nvim: #21252b）
HEADER_BG = "#313244"  # surface0（nvim: #2f343f）
CHIP_BG = "#45475a"    # surface1（nvim: #3b4252）
TITLE = "#cdd6f4"      # text    （nvim: #dcdfe4）
ACCENT = "#cba6f7"     # mauve   （nvim teal #53c9b8）: セクション名・tick・下線
KEY_FG = "#f5c2e7"     # pink    （nvim gold #e5c07b）: キー文字
DESC_FG = "#bac2de"    # subtext1（nvim: #abb2bf）
MUTED = "#7f849c"      # overlay1（nvim: #788094）: 凡例・フッター

FONT = "'Noto Sans CJK JP','Hiragino Sans','Yu Gothic',sans-serif"
MONO = "'DejaVu Sans Mono','SFMono-Regular',Menlo,monospace"

# --- レイアウト定数（nvim シートに一致） ---
CARD_W = 470
ROW_PITCH = 27
ROW_TOP = 50       # カード上端から最初の行までのオフセット
CARD_PAD_BOTTOM = 14
HEADER_H = 36
DESC_DX = 172      # キー chip 開始からの説明テキスト x オフセット（herdr は長いキーがあるため nvim の 154 より広め）
COLS_X = [42, 540, 1038]
TOP = 132          # カード開始 y
CARD_GAP = 22


def chip_w(key: str) -> int:
    # monospace 15px の概算幅（nvim の実測: 幅 ≈ 14 + n*8.7）
    return max(24, round(14 + len(key) * 8.7))


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def card(x: int, y: int, title: str, rows: list) -> tuple:
    h = ROW_TOP + len(rows) * ROW_PITCH + CARD_PAD_BOTTOM
    parts = [
        # 外枠
        f'<rect x="{x}" y="{y}" width="{CARD_W}" height="{h}" rx="14" fill="{CARD_BG}"/>',
        # ヘッダー帯（上角のみ丸め）
        f'<path d="M{x+14},{y} h{CARD_W-28} a14,14 0 0 1 14,14 v{HEADER_H-14} '
        f'h-{CARD_W} v-{HEADER_H-14} a14,14 0 0 1 14,-14 z" fill="{HEADER_BG}"/>',
        # セクション tick + タイトル
        f'<rect x="{x+20}" y="{y+10}" width="6" height="16" rx="3" fill="{ACCENT}"/>',
        f'<text x="{x+36}" y="{y+25}" font-size="19" font-weight="700" fill="{ACCENT}">{esc(title)}</text>',
    ]
    for i, (key, desc) in enumerate(rows):
        ry = y + ROW_TOP + i * ROW_PITCH
        parts.append(f'<rect x="{x+22}" y="{ry}" width="{chip_w(key)}" height="21" rx="6" fill="{CHIP_BG}"/>')
        parts.append(f'<text x="{x+30}" y="{ry+15}" font-size="15" font-family="{MONO}" fill="{KEY_FG}">{esc(key)}</text>')
        parts.append(f'<text x="{x+DESC_DX}" y="{ry+15}" font-size="15" fill="{DESC_FG}">{esc(desc)}</text>')
    return "\n".join(parts), h


# --- コンテンツ（config.toml のデフォルト + 明示バインドから）---
SEC_BASE = ("基本 / セッション", [
    ("Ctrl+b", "プレフィックスキー（先頭に押す）"),
    ("prefix ?", "ヘルプを表示"),
    ("prefix s", "設定を開く"),
    ("prefix q", "セッションからデタッチ"),
    ("prefix S-r", "config.toml を再読込"),
    ("prefix o", "通知先の pane へ移動"),
])
SEC_WS = ("ワークスペース", [
    ("prefix w", "ワークスペース選択"),
    ("prefix g", "goto でジャンプ"),
    ("prefix S-n", "新規ワークスペース"),
    ("prefix S-g", "新規 worktree"),
    ("prefix S-w", "名前を変更"),
    ("prefix S-d", "閉じる"),
    ("prefix S-←→", "前 / 次のワークスペース"),
])
SEC_TAB = ("タブ", [
    ("prefix c", "新規タブ"),
    ("prefix S-t", "名前を変更"),
    ("prefix S-x", "閉じる"),
    ("prefix p / n", "前 / 次のタブ"),
    ("prefix 1..9", "番号でタブ切替"),
])
SEC_PANE_MOVE = ("ペイン：移動・分割", [
    ("prefix h j k l", "左 下 上 右のペインへ"),
    ("prefix Tab", "次のペインへ巡回"),
    ("prefix S-Tab", "前のペインへ巡回"),
    ("prefix v", "縦に分割"),
    ("prefix -", "横に分割"),
    ("prefix z", "ズーム（全画面トグル）"),
])
SEC_PANE_OPS = ("ペイン：操作", [
    ("prefix x", "ペインを閉じる"),
    ("prefix r", "リサイズモード"),
    ("prefix S-p", "ペイン名を変更"),
    ("prefix e", "スクロールバックを編集"),
    ("prefix b", "サイドバー表示切替"),
])
SEC_DIRECT = ("ダイレクトキー（prefix 不要）", [
    ("Alt+Tab", "次のタブへ"),
    ("S-Alt+Tab", "前のタブへ"),
    ("C-Alt+] / [", "ペイン巡回 次 / 前"),
    ("C-S-Alt+] / [", "前 / 次のワークスペース"),
])
SEC_AGENT = ("エージェント / 未読", [
    ("prefix S-u", "未読へ順送り（blocked→done）"),
])

COLUMNS = [
    [SEC_BASE, SEC_WS],
    [SEC_TAB, SEC_PANE_MOVE],
    [SEC_PANE_OPS, SEC_DIRECT, SEC_AGENT],
]


def build() -> str:
    body = []
    max_bottom = TOP
    for x, sections in zip(COLS_X, COLUMNS):
        y = TOP
        for (title, rows) in sections:
            frag, h = card(x, y, title, rows)
            body.append(frag)
            y += h + CARD_GAP
        max_bottom = max(max_bottom, y - CARD_GAP)

    footer_y = max_bottom + 30
    height = footer_y + 22

    head = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1550" height="{height}" '
        f'viewBox="0 0 1550 {height}" font-family="{FONT}">',
        f'<rect width="1550" height="{height}" rx="18" fill="{PAGE_BG}"/>',
        f'<text x="42" y="60" font-size="34" font-weight="700" fill="{TITLE}">herdr チートシート</text>',
        f'<rect x="42" y="78" width="330" height="4" rx="2" fill="{ACCENT}"/>',
        f'<text x="42" y="106" font-size="16" fill="{MUTED}">'
        f'prefix = Ctrl+b（例: prefix n は Ctrl+b → n）　S- = Shift　C- = Ctrl　Alt- = Option</text>',
    ]
    footer = (
        f'<text x="42" y="{footer_y}" font-size="14" fill="{MUTED}">'
        f'herdr 0.7.1／config.toml のバインドを反映（コメント＝デフォルト有効）。数字キーはタブ直接切替。</text>'
    )
    return "\n".join([*head, *body, footer, "</svg>"]) + "\n"


def main() -> None:
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "herdr-cheatsheet.svg")
    with open(out, "w", encoding="utf-8") as f:
        f.write(build())
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
