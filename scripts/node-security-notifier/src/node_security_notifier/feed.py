"""Node 脆弱性 RSS (RSS 2.0) を FeedEntry のリストへパースする純粋関数。"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from node_security_notifier.models import FeedEntry


def parse_feed(xml_bytes: bytes) -> list[FeedEntry]:
    """RSS バイト列を FeedEntry のリストへ変換する。出現順を保持する。

    必須要素 (title, link, guid, pubDate) が欠けた item はスキップする。
    不正な XML は xml.etree.ElementTree.ParseError を送出する。
    """
    root = ET.fromstring(xml_bytes)
    entries: list[FeedEntry] = []
    for item in root.findall("./channel/item"):
        guid = _text(item, "guid")
        title = _text(item, "title")
        link = _text(item, "link")
        pub_date = _text(item, "pubDate")
        if not (guid and title and link and pub_date):
            continue
        entries.append(FeedEntry(guid=guid, title=title, link=link, pub_date=pub_date))
    return entries


def _text(item: ET.Element, tag: str) -> str:
    el = item.find(tag)
    if el is None or el.text is None:
        return ""
    return el.text.strip()
