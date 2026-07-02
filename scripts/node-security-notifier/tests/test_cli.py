"""cli オーケストレーションの仕様テスト（依存注入、モック不使用）。"""

from __future__ import annotations

from pathlib import Path

from node_security_notifier.cli import run
from node_security_notifier.notify import Notification
from node_security_notifier.state import load_seen, save_seen

FIXTURE = Path(__file__).parent / "fixtures" / "sample_feed.xml"
GUID_JUNE = "https://nodejs.org/en/blog/vulnerability/june-2026-security-releases"
GUID_MARCH = "https://nodejs.org/en/blog/vulnerability/march-2026-security-releases"


class Recorder:
    """通知を記録する test double（モックフレームワーク不使用）。"""

    def __init__(self) -> None:
        self.sent: list[Notification] = []

    def __call__(self, n: Notification) -> None:
        self.sent.append(n)


def _fetch_ok() -> bytes:
    return FIXTURE.read_bytes()


class TestRun:
    def test_first_run_seeds_without_notifying(self, tmp_path: Path) -> None:
        state = tmp_path / "seen.json"
        rec = Recorder()
        rc = run(fetcher=_fetch_ok, notifier=rec, state_path=state)
        assert rc == 0
        assert rec.sent == []
        assert load_seen(state) == {GUID_JUNE, GUID_MARCH}

    def test_notifies_only_new_entries(self, tmp_path: Path) -> None:
        state = tmp_path / "seen.json"
        save_seen(state, {GUID_MARCH})  # march は既読、june が新着
        rec = Recorder()
        rc = run(fetcher=_fetch_ok, notifier=rec, state_path=state)
        assert rc == 0
        assert [n.subtitle for n in rec.sent] == ["June 2026 Security Releases"]
        assert load_seen(state) == {GUID_JUNE, GUID_MARCH}

    def test_no_notification_when_all_seen(self, tmp_path: Path) -> None:
        state = tmp_path / "seen.json"
        save_seen(state, {GUID_JUNE, GUID_MARCH})
        rec = Recorder()
        rc = run(fetcher=_fetch_ok, notifier=rec, state_path=state)
        assert rc == 0
        assert rec.sent == []

    def test_network_failure_is_safe(self, tmp_path: Path) -> None:
        state = tmp_path / "seen.json"
        save_seen(state, {GUID_MARCH})

        def _fetch_fail() -> bytes:
            raise OSError("network down")

        rec = Recorder()
        rc = run(fetcher=_fetch_fail, notifier=rec, state_path=state)
        assert rc == 1
        assert rec.sent == []
        assert load_seen(state) == {GUID_MARCH}  # 状態は不変

    def test_parse_failure_is_safe(self, tmp_path: Path) -> None:
        state = tmp_path / "seen.json"
        save_seen(state, {GUID_MARCH})

        def _fetch_garbage() -> bytes:
            return b"<rss><channel><item>"

        rec = Recorder()
        rc = run(fetcher=_fetch_garbage, notifier=rec, state_path=state)
        assert rc == 1
        assert rec.sent == []
        assert load_seen(state) == {GUID_MARCH}

    def test_empty_feed_is_safe(self, tmp_path: Path) -> None:
        state = tmp_path / "seen.json"
        save_seen(state, {GUID_MARCH})

        def _fetch_empty() -> bytes:
            return b'<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'

        rec = Recorder()
        rc = run(fetcher=_fetch_empty, notifier=rec, state_path=state)
        assert rc == 1
        assert rec.sent == []
        assert load_seen(state) == {GUID_MARCH}
