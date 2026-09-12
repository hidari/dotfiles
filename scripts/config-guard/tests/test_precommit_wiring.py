"""pre-commit hook の配線テスト。

CI ミラーを持たない hook や、健全時の出力が「何も見ていない」と区別できない hook は、
配線が外れても誰も気づかない。ここで構造として縛る。

YAML は safe_load で構造として読む (グローバル CLAUDE.md の MUST: 設定のデータ構造を
検証するときは定義を source / import して言語自身に解釈させる。行パースの前例は
scripts/tests/ast-grep-wiring-probe.py の docstring にある通り false pass / false fail
の両方を起こした)。
"""

from __future__ import annotations

import re
from typing import Any

import yaml

from tests.conftest import REPO_ROOT

_PRECOMMIT_CONFIG_PATH = REPO_ROOT / ".pre-commit-config.yaml"


def _single_hook(hook_id: str) -> dict[str, Any]:
    """id で hook を 1 つ取り出す。消えた場合も複製された場合もここで落とす。

    0 件を空リストで返すと、後続の assert が 1 つも実行されないまま緑になる。
    """
    with _PRECOMMIT_CONFIG_PATH.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    hooks: list[dict[str, Any]] = [
        hook
        for repo in data.get("repos", [])
        for hook in repo.get("hooks", [])
        if hook.get("id") == hook_id
    ]
    assert len(hooks) == 1
    return hooks[0]


def test_precommit_scan_hook_always_runs() -> None:
    # 発火条件を持つ限り「入力ファイルの編集で発火しない検査」が構造的に作れてしまう。
    # always_run: true はその集合を空にする唯一の閉じた形なので、値そのものを pin する。
    # files 方式へ戻ると、検査追加のたびに scan() への配線と files への追記が独立した
    # 手作業になり、追記漏れが silent に起きる (mise で実際に起きた)
    assert _single_hook("config-guard-scan").get("always_run") is True


def test_issue_ref_notation_hook_checks_the_diff_only() -> None:
    # 入口の選択と CI ミラーを張らない理由は .pre-commit-config.yaml の hook 直上が持つ。
    # ここで縛るのは、その設計が壊れる 3 つの形だけ。
    hook = _single_hook("issue-ref-notation")
    entry = hook["entry"]
    assert "issue-id.py" in entry
    # 全走査の入口へ変わると既存違反で常時赤になり、hook ごと外される
    assert "--check-diff" in entry
    # 差分は引数で渡らないので pre-commit がファイル名を渡す形にしない。
    # always_run が外れると「Issue を触らないコミットでは走らない」に化ける
    assert hook.get("pass_filenames") is False
    assert hook.get("always_run") is True
    # パスの実在は縛れない。検査器は apm の deploy 先に在り fresh clone と CI には
    # 存在しないので、実在を assert すると CI が赤くなる。不在時に無音で素通りしない
    # ことは python3 自身の exit 2 が担保するため、ここは entry の形だけを見る


def test_issue_scoped_artifacts_hook_matches_upstream_default_paths_only() -> None:
    # issue-scoped-artifacts hook の健全時の出力は常に "(no files to check)Skipped"
    # である。移行で docs/superpowers/{plans,specs}/ が消えたため、通常のコミットでも
    # --all-files でも永久に 1 件もマッチしない。そのため「files の正規表現が正しく
    # 効いている」状態と「typo が入った」「hook ブロックごと消えた/複製された」
    # 「exclude や types が事故で付いた」状態がすべて同一の出力になり、実装時の
    # 1 回きりの手動 live smoke 以外にこれを守る仕組みが無かった。
    # 正規表現の literal はここに再掲せず .pre-commit-config.yaml から読んでコンパイルする
    pattern = re.compile(_single_hook("issue-scoped-artifacts")["files"])

    # positive: 上流 superpowers (brainstorming / writing-plans) の既定パス
    assert pattern.search("docs/superpowers/plans/2026-08-02-example.md")
    assert pattern.search("docs/superpowers/specs/2026-08-02-example-design.md")

    # negative: マッチしてはいけない経路。無いと「何をしても落ちる hook」と区別できない
    assert not pattern.search("docs/superpowers/archive/2026-07-03-session-handoff-design.md")
    assert not pattern.search("docs/issues/16_example/16-spec.md")
    assert not pattern.search("docs/issues/closed/15_example/15-plan.md")
