"""index.json から security リリースの版を取り出す仕様テスト。

空の一覧や形の崩れた要素を「該当なし」にしないことが要点。該当なしへ潰すと、判定が
壊れていても状態ファイルが「遅れなし」で上書きされ、プローブが黙る。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from node_security_notifier.index import IndexFormatError, parse_index

FIXTURE = Path(__file__).parent / "fixtures" / "index_excerpt.json"


def _entry(version: object = "v24.22.1", security: object = True) -> dict[str, object]:
    return {"version": version, "date": "2026-10-20", "lts": "Krypton", "security": security}


class TestParseIndex:
    def test_returns_security_versions_in_order(self) -> None:
        assert parse_index(FIXTURE.read_bytes()) == [
            "26.12.1",
            "25.8.2",
            "24.22.1",
            "24.18.1",
            "22.22.0",
        ]

    @pytest.mark.parametrize(
        "raw",
        [
            pytest.param(b"<html>not json</html>", id="not-json"),
            pytest.param(b'{"version": "v24.22.1"}', id="top-level-not-list"),
            pytest.param(b"[]", id="empty-list"),
            pytest.param(json.dumps([_entry(version="24.22.1")]).encode(), id="version-without-v"),
            pytest.param(json.dumps([_entry(version="v24.22")]).encode(), id="version-two-parts"),
            pytest.param(json.dumps([_entry(version=24)]).encode(), id="version-not-str"),
            pytest.param(
                json.dumps([{k: v for k, v in _entry().items() if k != "version"}]).encode(),
                id="version-missing",
            ),
            pytest.param(json.dumps([_entry(security="true")]).encode(), id="security-str"),
            pytest.param(json.dumps([_entry(security=1)]).encode(), id="security-int"),
            pytest.param(
                json.dumps([{k: v for k, v in _entry().items() if k != "security"}]).encode(),
                id="security-missing",
            ),
            pytest.param(json.dumps(["v24.22.1"]).encode(), id="element-not-object"),
            pytest.param(
                json.dumps(
                    [_entry(security=False), _entry(version="v24.22.0", security=False)]
                ).encode(),
                id="no-security-release",
            ),
        ],
    )
    def test_malformed_input_is_an_error_not_an_empty_result(self, raw: bytes) -> None:
        with pytest.raises(IndexFormatError):
            parse_index(raw)

    def test_one_malformed_element_fails_the_whole_list(self) -> None:
        raw = json.dumps([_entry(), _entry(version="v24.22.0", security=None)]).encode()
        with pytest.raises(IndexFormatError):
            parse_index(raw)
