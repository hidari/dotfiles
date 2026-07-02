"""feed パースの仕様テスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from node_security_notifier.feed import parse_feed

FIXTURE = Path(__file__).parent / "fixtures" / "sample_feed.xml"


class TestParseFeed:
    def test_parses_valid_items_in_order(self) -> None:
        entries = parse_feed(FIXTURE.read_bytes())
        assert [(e.guid, e.title) for e in entries] == [
            (
                "https://nodejs.org/en/blog/vulnerability/june-2026-security-releases",
                "June 2026 Security Releases",
            ),
            (
                "https://nodejs.org/en/blog/vulnerability/march-2026-security-releases",
                "March 2026 Security Releases",
            ),
        ]

    def test_skips_items_missing_required_fields(self) -> None:
        entries = parse_feed(FIXTURE.read_bytes())
        assert all(e.guid for e in entries)
        assert len(entries) == 2

    def test_raises_on_malformed_xml(self) -> None:
        import xml.etree.ElementTree as ET

        with pytest.raises(ET.ParseError):
            parse_feed(b"<rss><channel><item>")
