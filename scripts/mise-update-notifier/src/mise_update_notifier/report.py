"""報告本文 (Markdown) の整形。

危険度で節を分ける。互換範囲の更新はそのまま上げてよいことが多いので config へ貼れる
pin 行まで出し、メジャー越えは判断が要るので事実の提示に留めて書き換えを勧めない。

報告するかどうかは互換範囲の更新の有無だけで決める。メジャー越えは「上げない」と決めた
まま残り続けうるので、それを報告の条件にすると Issue が永久に閉じず、常時開いた通知は
やがて見られなくなる。単独では黙り、Issue が立つときだけ付録として載せる。
"""

from __future__ import annotations

from mise_update_notifier.versions import (
    ToolStatus,
    has_compatible_update,
    has_major_update,
)


def _table(rows: list[tuple[str, str, str]]) -> str:
    header = ["| tool | 現在 | 最新 |", "| --- | --- | --- |"]
    body = [f"| {tool} | {current} | {latest} |" for tool, current, latest in rows]
    return "\n".join(header + body)


def _fence(language: str, lines: list[str]) -> str:
    return "\n".join([f"```{language}", *lines, "```"])


def render_body(statuses: list[ToolStatus], config_path: str) -> str:
    """更新の無いツールを除いた報告本文を返す。報告対象が無ければ空文字列。"""
    compatible = [s for s in statuses if has_compatible_update(s)]
    if not compatible:
        return ""

    # 段落の区切りは join が持つ。各要素は 1 ブロックで、末尾に空行を足さない。
    blocks = [
        "## 同メジャー更新",
        "破壊的変更を跨がない範囲の更新。",
        _table([(s.tool, s.pinned, s.compatible_latest) for s in compatible]),
        f"`{config_path}` を書き換える:",
        _fence("toml", [f'{s.tool} = "{s.compatible_latest}"' for s in compatible]),
        "反映する:",
        _fence("sh", ["mise install"]),
    ]

    major = [s for s in statuses if has_major_update(s)]
    if major:
        blocks += [
            "## メジャー越え",
            "破壊的変更を含みうるので、上げるかは個別に判断する。"
            "この節は単独では報告されず、同メジャー更新があるときだけ併せて載る。",
            _table([(s.tool, s.pinned, s.absolute_latest) for s in major]),
        ]

    return "\n\n".join(blocks) + "\n"
