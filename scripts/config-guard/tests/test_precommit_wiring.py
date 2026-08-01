"""pre-commit の config-guard-scan hook の配線テスト。

hook は files の列挙ではなく always_run: true で毎コミット発火する。files 方式は
「検査ごとの入力パスの選択肢」の開いた列挙で、検査追加のたびに scan() への配線と
files への追記が独立した手作業になり、追記漏れが silent に起きる (mise で実際に
起きた)。always_run が外れて files 方式へ戻ると同じ穴が再発するため、ここで pin する。

YAML は safe_load で構造として読む (グローバル CLAUDE.md の MUST: 設定のデータ構造を
検証するときは定義を source / import して言語自身に解釈させる。行パースの前例は
scripts/tests/ast-grep-wiring-probe.py の docstring にある通り false pass / false fail
の両方を起こした)。
"""

from __future__ import annotations

import re

import yaml

from tests.conftest import REPO_ROOT

_PRECOMMIT_CONFIG_PATH = REPO_ROOT / ".pre-commit-config.yaml"


def test_precommit_scan_hook_always_runs() -> None:
    # 発火条件を持つ限り「入力ファイルの編集で発火しない検査」が構造的に作れてしまう。
    # always_run: true はその集合を空にする唯一の閉じた形なので、値そのものを pin する
    with _PRECOMMIT_CONFIG_PATH.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    hooks = [
        hook
        for repo in data.get("repos", [])
        for hook in repo.get("hooks", [])
        if hook.get("id") == "config-guard-scan"
    ]
    # hook が消えた/複製された場合も silent pass にせずここで落とす
    assert len(hooks) == 1
    assert hooks[0].get("always_run") is True


def test_issue_scoped_artifacts_hook_matches_upstream_default_paths_only() -> None:
    # issue-scoped-artifacts hook の健全時の出力は常に "(no files to check)Skipped"
    # である。移行で docs/superpowers/{plans,specs}/ が消えたため、通常のコミットでも
    # --all-files でも永久に 1 件もマッチしない。そのため「files の正規表現が正しく
    # 効いている」状態と「typo が入った」「hook ブロックごと消えた/複製された」
    # 「exclude や types が事故で付いた」状態がすべて同一の出力になり、実装時の
    # 1 回きりの手動 live smoke 以外にこれを守る仕組みが無かった。
    # 正規表現の literal はここに再掲せず .pre-commit-config.yaml から読んでコンパイルする
    with _PRECOMMIT_CONFIG_PATH.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    hooks = [
        hook
        for repo in data.get("repos", [])
        for hook in repo.get("hooks", [])
        if hook.get("id") == "issue-scoped-artifacts"
    ]
    # hook が消えた/複製された場合も silent pass にせずここで落とす
    assert len(hooks) == 1
    pattern = re.compile(hooks[0]["files"])

    # positive: 上流 superpowers (brainstorming / writing-plans) の既定パス
    assert pattern.search("docs/superpowers/plans/2026-08-02-example.md")
    assert pattern.search("docs/superpowers/specs/2026-08-02-example-design.md")

    # negative: マッチしてはいけない経路。無いと「何をしても落ちる hook」と区別できない
    assert not pattern.search("docs/superpowers/archive/2026-07-03-session-handoff-design.md")
    assert not pattern.search("docs/issues/16_example/16-spec.md")
    assert not pattern.search("docs/issues/closed/15_example/15-plan.md")
