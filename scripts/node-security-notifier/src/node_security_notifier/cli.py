"""取得 -> 検証 -> 保存 のオーケストレーション。

pin との比較はここでは行わない。比較は SessionStart のプローブが現在の pin で行うので、
pin を上げた直後に古い判定が残って誤報になることが無い。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

from node_security_notifier.fetch import fetch_index
from node_security_notifier.index import IndexFormatError, parse_index
from node_security_notifier.state import STATE_RELPATH, save_status

logger = logging.getLogger("node_security_notifier")


def run(
    *,
    fetcher: Callable[[], bytes],
    state_path: Path,
    clock: Callable[[], float] = time.time,
) -> int:
    """1 回分の取得〜保存を実行する。戻り値はプロセス終了コード。

    失敗したときは状態ファイルを書かない。取得時刻が古いまま残ることで、プローブが
    判定の停止を告げられる。
    """
    try:
        raw = fetcher()
    except OSError as exc:
        logger.error("配布一覧の取得に失敗しました: %s", exc)
        return 1

    try:
        versions = parse_index(raw)
    except IndexFormatError as exc:
        logger.error("配布一覧の形が想定と違います: %s", exc)
        return 1

    save_status(state_path, fetched_at=int(clock()), security_versions=versions)
    logger.info("security リリース %d 件を記録しました", len(versions))
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI エントリポイント。本番依存を結線して run を呼ぶ。"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return run(fetcher=fetch_index, state_path=Path.home() / STATE_RELPATH)
