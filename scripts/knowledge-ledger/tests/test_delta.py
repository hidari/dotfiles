"""delta の3規則を小さな git リポジトリで1件ずつ確かめる。"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from knowledge_ledger.delta import build_delta, main

TODAY = "2026-12-01"
ISSUE_PATH = "docs/issues/ISSUE-9_x/issue.md"
BASE_MD = "# 知見\n\n- 既存の箇条\n"


def git(repo: Path, *args: str) -> None:
    # 使い捨てのリポジトリしか触らないので、GIT_ で始まる変数を選ばずに全部落とす
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def make_repo(tmp_path: Path, head_md: str) -> Path:
    """origin/main を base_md の状態に置き、作業ブランチで head_md へ書き換えた小さなリポジトリ"""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    # CI には git の identity が無いのでリポジトリ側へ書く
    git(repo, "config", "user.name", "tester")
    git(repo, "config", "user.email", "test@example.com")
    path = repo / ISSUE_PATH
    path.parent.mkdir(parents=True)
    path.write_text(BASE_MD, encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "base")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(repo, "checkout", "-q", "-b", "work")
    path.write_text(head_md, encoding="utf-8")
    git(repo, "commit", "-q", "-am", "work")
    return repo


def ledger_item(text: str) -> dict[str, Any]:
    return {"id": "K9-001", "order": 1, "issue": "ISSUE-9", "text": text}


def test_new_top_level_bullet_becomes_new_item(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, BASE_MD + "- 新しい箇条\n  - 子の行\n")
    delta = build_delta(str(repo), [], TODAY)
    assert delta["appended"] == []
    [item] = delta["new"]
    assert item["id"] == "K9-001"
    assert item["issue"] == "ISSUE-9"
    assert item["section"] == "知見"
    assert item["text"] == "- 新しい箇条\n  - 子の行"
    assert item["added"] == TODAY


def test_child_added_to_ledger_bullet_is_appended(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, BASE_MD + "  - 足した子\n")
    delta = build_delta(str(repo), [ledger_item("- 既存の箇条")], TODAY)
    assert delta["new"] == []
    assert delta["appended"] == [
        {"id": "K9-001", "new_text": "- 既存の箇条\n  - 足した子", "added_children": ["- 足した子"]}
    ]


def test_child_added_to_bullet_missing_from_ledger_becomes_new_item(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, BASE_MD + "  - 足した子\n")
    delta = build_delta(str(repo), [], TODAY)
    assert delta["appended"] == []
    [item] = delta["new"]
    assert item["id"] == "K9-001"
    assert item["text"] == "- 既存の箇条\n  - 足した子"
    assert item["parent_existing"] is True


def test_main_takes_today_and_writes_delta(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, BASE_MD + "- 新しい箇条\n")
    base_path, out_path = tmp_path / "base.json", tmp_path / "delta.json"
    base_path.write_text("[]", encoding="utf-8")
    assert main([str(repo), str(base_path), str(out_path), "--today", TODAY]) == 0
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["new"][0]["added"] == TODAY


def test_inherited_git_location_env_does_not_leak(tmp_path: Path, monkeypatch: Any) -> None:
    """pre-commit の hook は GIT_DIR や GIT_INDEX_FILE を付けて走る。継承すると使い捨ての
    リポジトリではなく本体の index と設定を書き換える (2026-11-15 に worktree で踏んだ)"""
    decoy = tmp_path / "decoy"
    monkeypatch.setenv("GIT_DIR", str(decoy / "git"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(decoy / "index"))
    repo = make_repo(tmp_path, BASE_MD + "- 新しい箇条\n")
    d = build_delta(str(repo), [ledger_item("- 既存の箇条")], TODAY)
    assert [i["text"] for i in d["new"]] == ["- 新しい箇条"]
    assert not decoy.exists()
