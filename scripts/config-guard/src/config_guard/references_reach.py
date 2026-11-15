"""references が根から参照の連鎖で届くかを検査する。

references は常時ロードされず、名指しした規範を読んだ読み手が開いて初めて効く。名指しの
無い references は置いても誰も開かないので、書いた知見を消したのと同じになる。壊れ方は
参照が 0 件という沈黙で、参照の実在を見る instruction_refs からは見えない (存在しない
参照は報告できるが、存在しない名指しは報告できない)。

- 根: 常時層の CLAUDE.md と rules (paths の有無を問わない。paths 付きも Read で発火する)
- 辺: 本文中のバッククォート記法の `~/.claude/references/<file>.md`。抽出の規約
  (フェンス内を除く・記法で区別する) は instruction_refs と共有する
- 届いた references からの名指しも辺に数える。索引や分割した参照は、親を開いた読み手から届く

既知の限界: 届くことは読まれることの保証ではない。名指しの文面がトリガを書いていなければ、
読み手は開く場面に気づけない。それは文面のレビューが見る。
"""

from __future__ import annotations

from pathlib import Path

from config_guard.instruction_budget import CLAUDE_MD_PATH, RULES_GLOB
from config_guard.instruction_refs import extract_home_refs, is_checkable_ref, repo_path
from config_guard.models import Finding

REFERENCES_GLOB = "home/.claude/references/*.md"


def _named_references(text: str) -> set[str]:
    """本文が名指しする references のリポジトリ相対パスを返す。"""
    paths = {repo_path(ref) for ref in extract_home_refs(text) if is_checkable_ref(ref)}
    return {path for path in paths if Path(path).match(REFERENCES_GLOB)}


def reached_references(repo_root: str) -> set[str]:
    """根から参照の連鎖で届く references のリポジトリ相対パスを返す。"""
    root = Path(repo_root)
    roots = [root / CLAUDE_MD_PATH, *sorted(root.glob(RULES_GLOB))]
    frontier = [path for path in roots if path.is_file()]
    reached: set[str] = set()

    while frontier:
        text = frontier.pop().read_text(encoding="utf-8")
        for rel in _named_references(text) - reached:
            target = root / rel
            # 実在しない名指しは instruction_refs が報告する。ここでは辿らない
            if target.is_file():
                reached.add(rel)
                frontier.append(target)

    return reached


def check_references_reach(repo_root: str) -> list[Finding]:
    """根から届かない references を報告する。"""
    root = Path(repo_root)
    reached = reached_references(repo_root)
    return [
        Finding(
            rel,
            Path(rel).name,
            "CLAUDE.md と rules から参照の連鎖で届かない。"
            "名指しの無い references は誰も開かないので、置いた知見が黙って効かなくなる",
        )
        for rel in sorted(str(p.relative_to(root)) for p in root.glob(REFERENCES_GLOB))
        if rel not in reached
    ]
