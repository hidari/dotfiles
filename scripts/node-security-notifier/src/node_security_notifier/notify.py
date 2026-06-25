"""新着エントリから macOS 通知を組み立て osascript で送出する。

通知文はユーザー向け（外部）なので英語。値は osascript の argv で渡し、
AppleScript 文字列リテラルのエスケープを不要にする。
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from node_security_notifier.models import FeedEntry

_TITLE = "Node.js Security Release"
_VULN_PAGE = "See nodejs.org/en/blog/vulnerability"


@dataclass(frozen=True)
class Notification:
    """1 件の macOS 通知。title/subtitle/body はそのまま表示される。"""

    title: str
    subtitle: str
    body: str


def build_notifications(entries: list[FeedEntry], max_individual: int) -> list[Notification]:
    """先頭 max_individual 件を個別通知化し、超過分はサマリ 1 件にまとめる。"""
    notifications = [
        Notification(title=_TITLE, subtitle=entry.title, body=entry.link)
        for entry in entries[:max_individual]
    ]
    overflow = len(entries) - max_individual
    if overflow > 0:
        notifications.append(
            Notification(
                title=_TITLE,
                subtitle=f"{overflow} more security release(s)",
                body=_VULN_PAGE,
            )
        )
    return notifications


def build_osascript_args(n: Notification) -> list[str]:
    """値を argv で渡す osascript コマンド配列を組み立てる（エスケープ不要）。"""
    return [
        "osascript",
        "-e",
        "on run argv",
        "-e",
        "display notification (item 1 of argv) with title "
        "(item 2 of argv) subtitle (item 3 of argv)",
        "-e",
        "end run",
        n.body,
        n.title,
        n.subtitle,
    ]


def send_notification(n: Notification) -> None:
    """osascript で通知を送出する。失敗時は subprocess.CalledProcessError を送出。"""
    subprocess.run(build_osascript_args(n), check=True)
