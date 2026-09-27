"""notify（通知組立）の仕様テスト。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from node_security_notifier.models import FeedEntry
from node_security_notifier.notify import (
    Notification,
    build_notifications,
    build_osascript_args,
    send_notification,
)

E1 = FeedEntry("g1", "June 2026 Security Releases", "https://x/1", "d")
E2 = FeedEntry("g2", "March 2026 Security Releases", "https://x/2", "d")
E3 = FeedEntry("g3", "Jan 2026 Security Releases", "https://x/3", "d")
E4 = FeedEntry("g4", "Dec 2025 Security Releases", "https://x/4", "d")


class TestBuildNotifications:
    def test_one_per_entry_within_limit(self) -> None:
        out = build_notifications([E1, E2], max_individual=3)
        assert len(out) == 2
        assert out[0] == Notification(
            title="Node.js Security Release",
            subtitle="June 2026 Security Releases",
            body="https://x/1",
        )

    def test_summary_appended_on_overflow(self) -> None:
        out = build_notifications([E1, E2, E3, E4], max_individual=3)
        assert len(out) == 4
        assert out[3] == Notification(
            title="Node.js Security Release",
            subtitle="1 more security release(s)",
            body="See nodejs.org/en/blog/vulnerability",
        )

    def test_empty_returns_empty(self) -> None:
        assert build_notifications([], max_individual=3) == []


class TestBuildOsascriptArgs:
    def test_passes_values_via_argv(self) -> None:
        n = Notification(title="T", subtitle="S", body="B")
        assert build_osascript_args(n) == [
            "osascript",
            "-e",
            "on run argv",
            "-e",
            "display notification (item 1 of argv) with title "
            "(item 2 of argv) subtitle (item 3 of argv)",
            "-e",
            "end run",
            "B",
            "T",
            "S",
        ]


class TestSendNotification:
    def test_raises_on_nonzero_exit(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # 偽の osascript を PATH の先頭に置く。終了コードを 1 以外にするのは、実物の
        # osascript ではなくこの偽物が失敗したことを returncode で確かめるため
        fake = tmp_path / "osascript"
        fake.write_text("#!/bin/sh\nexit 3\n", encoding="utf-8")
        fake.chmod(0o755)
        monkeypatch.setenv("PATH", str(tmp_path), prepend=os.pathsep)
        n = Notification(title="T", subtitle="S", body="B")

        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            send_notification(n)

        assert exc_info.value.returncode == 3
        assert exc_info.value.cmd == build_osascript_args(n)
