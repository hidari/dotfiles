"""references が根から参照の連鎖で届くかを検査する。

references は常時ロードされず、名指しした規範を読んだ読み手が開いて初めて効く。名指しの
無い references は置いても誰も開かないので、書いた知見を消したのと同じになる。壊れ方は
参照が0件という沈黙で、参照の実在を見る instruction_refs からは見えない (存在しない
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

from config_guard.instruction_refs import (
    REFERENCES_GLOB,
    extract_home_refs,
    is_checkable_ref,
    repo_path,
    source_files,
)
from config_guard.models import Finding


def _is_reference(rel: str) -> bool:
    return Path(rel).match(REFERENCES_GLOB)


def _named_references(text: str) -> set[str]:
    """本文が名指しする references のリポジトリ相対パスを返す。"""
    paths = {repo_path(ref) for ref in extract_home_refs(text) if is_checkable_ref(ref)}
    return {path for path in paths if _is_reference(path)}


def _reached(texts: dict[str, str]) -> set[str]:
    """{リポジトリ相対パス: 本文} のうち、根から参照の連鎖で届く references を返す。

    母集団は instruction_refs.source_files が canonical を持つ。参照検査と別の集合を見ると、
    片方だけが新しい置き場を見落としたまま両方緑になるため。根は references 以外 (常時層と rules)
    """
    frontier = [rel for rel in texts if not _is_reference(rel)]
    reached: set[str] = set()

    while frontier:
        for rel in _named_references(texts[frontier.pop()]) - reached:
            # 実在しない名指しは instruction_refs が報告する。ここでは辿らない
            if rel in texts:
                reached.add(rel)
                frontier.append(rel)

    return reached


def reached_references(repo_root: str) -> set[str]:
    """根から参照の連鎖で届く references のリポジトリ相対パスを返す。"""
    return _reached(source_files(repo_root))


def check_references_reach(repo_root: str) -> list[Finding]:
    """根から届かない references を報告する。"""
    texts = source_files(repo_root)
    reached = _reached(texts)
    return [
        Finding(
            rel,
            Path(rel).name,
            "CLAUDE.md と rules から参照の連鎖で届かない。"
            "名指しの無い references は誰も開かないので、置いた知見が黙って効かなくなる",
        )
        for rel in sorted(texts)
        if _is_reference(rel) and rel not in reached
    ]
