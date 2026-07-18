"""報告本文 (Markdown) の整形。

危険度で節を分ける。互換範囲の更新はそのまま上げてよいことが多いので config へ貼れる
pin 行まで出し、メジャー越えは判断が要るので事実の提示に留めて書き換えを勧めない。
"""

from __future__ import annotations

from mise_update_notifier.versions import (
    ToolStatus,
    has_compatible_update,
    has_major_update,
)


def _table(rows: list[tuple[str, str, str]]) -> list[str]:
    lines = ["| tool | 現在 | 最新 |", "| --- | --- | --- |"]
    lines += [f"| {tool} | {current} | {latest} |" for tool, current, latest in rows]
    return lines


def render_body(statuses: list[ToolStatus], config_path: str) -> str:
    """更新の無いツールを除いた報告本文を返す。報告対象が無ければ空文字列。"""
    compatible = [s for s in statuses if has_compatible_update(s)]
    major = [s for s in statuses if has_major_update(s)]
    if not compatible and not major:
        return ""

    lines: list[str] = []

    if compatible:
        lines.append("## 同メジャー更新")
        lines.append("")
        lines.append("破壊的変更を跨がない範囲の更新。")
        lines.append("")
        lines += _table([(s.tool, s.pinned, s.compatible_latest) for s in compatible])
        lines.append("")
        lines.append(f"`{config_path}` を書き換える:")
        lines.append("")
        lines.append("```toml")
        lines += [f'{s.tool} = "{s.compatible_latest}"' for s in compatible]
        lines.append("```")
        lines.append("")
        lines.append("反映する:")
        lines.append("")
        lines.append("```sh")
        lines.append("mise install")
        lines.append("```")
        lines.append("")

    if major:
        lines.append("## メジャー越え")
        lines.append("")
        lines.append("破壊的変更を含みうるので、上げるかは個別に判断する。")
        lines.append("")
        lines += _table([(s.tool, s.pinned, s.absolute_latest) for s in major])
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
