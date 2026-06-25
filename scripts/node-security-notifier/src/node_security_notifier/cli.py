"""取得 -> パース -> 差分 -> 通知 -> 保存 のオーケストレーション。"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path

from node_security_notifier.diff import new_entries
from node_security_notifier.feed import parse_feed
from node_security_notifier.fetch import FEED_URL, fetch_feed
from node_security_notifier.notify import Notification, build_notifications, send_notification
from node_security_notifier.state import load_seen, save_seen

logger = logging.getLogger("node_security_notifier")

DEFAULT_STATE_PATH = Path.home() / ".local" / "state" / "node-security-notifier" / "seen.json"
MAX_INDIVIDUAL = 3


def run(
    *,
    fetcher: Callable[[], bytes],
    notifier: Callable[[Notification], None],
    state_path: Path,
    max_individual: int = MAX_INDIVIDUAL,
) -> int:
    """1 回分の取得〜通知を実行する。戻り値はプロセス終了コード。"""
    try:
        raw = fetcher()
    except OSError as exc:
        logger.error("フィード取得に失敗しました: %s", exc)
        return 1

    try:
        current = parse_feed(raw)
    except ET.ParseError as exc:
        logger.error("フィードのパースに失敗しました: %s", exc)
        return 1

    if not current:
        logger.error("フィードが空でした。状態は更新しません")
        return 1

    current_guids = {e.guid for e in current}
    seen = load_seen(state_path)
    if not seen:
        save_seen(state_path, current_guids)
        logger.info("初回実行のため現状を seed しました (%d 件)", len(current))
        return 0

    fresh = new_entries(current, seen)
    for notification in build_notifications(fresh, max_individual):
        notifier(notification)
    save_seen(state_path, seen | current_guids)
    logger.info("新着 %d 件を処理しました", len(fresh))
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI エントリポイント。本番依存を結線して run を呼ぶ。"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return run(
        fetcher=lambda: fetch_feed(FEED_URL),
        notifier=send_notification,
        state_path=DEFAULT_STATE_PATH,
    )
