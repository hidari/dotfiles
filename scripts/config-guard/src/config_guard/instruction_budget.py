"""常時ロードされる指示ファイルの総バイト数を予算内に保つ検査。

CLAUDE.md は追記で膨らみ続ける (実測: 2026-08-12 の 36,599B から 9 日で 52,766B)。
一回きりの削減は数週間で食われるため、削減量ではなく上限を検査で固定する。

「常時ロード」の判定は Claude Code の実測仕様に従う。

- User スコープの CLAUDE.md は session_start で必ずロードされる
- `~/.claude/rules/*.md` は paths frontmatter が無いときだけ session_start でロードされる
- paths を持つ rules は該当パターンのファイルに触れたときだけロードされる

常時層のコストは session_start だけでなく subagent の dispatch ごとにも払う
(subagent がツールを一切使わずに CLAUDE.md の本文を引用できることを実測した)。
この経路は InstructionsLoaded フックのログに現れないため、ログでは測れない。

覆う範囲は dotfiles が管理する User スコープの指示だけ。プロジェクトごとの CLAUDE.md、
skill の description、auto memory の MEMORY.md も常時ロードされるが、リポジトリの外にあるか
コストの単位が違うため対象にしない。予算内であることは常時ロード総量の保証ではない。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from config_guard.models import Finding

# 常時ロード層の上限 (バイト)。canonical はここだけに置く。
# 移設でカテゴリを切り出したら同時に下げる (幅は test_budget_tracks_the_real_repo_closely が縛る)。
ALWAYS_LOADED_BUDGET_BYTES = 33294

CLAUDE_MD_PATH = "home/.claude/CLAUDE.md"
RULES_GLOB = "home/.claude/rules/*.md"

_FRONTMATTER_OPEN = "---\n"


def is_always_loaded_rule(text: str) -> bool:
    """rules の本文が paths frontmatter を持たない (= 常時ロードされる) かを返す。

    frontmatter は YAML として解釈する。regex で `paths:` を探すと本文中の記述を
    frontmatter と誤読し、正当な scoped rules を予算へ計上してしまう。

    frontmatter が壊れているときは常時ロード扱い (予算へ計上) にする。
    計上漏れは予算を無言ですり抜けるので、誤るなら厳しい側へ倒す。
    """
    if not text.startswith(_FRONTMATTER_OPEN):
        return True
    end = text.find("\n---", len(_FRONTMATTER_OPEN) - 1)
    if end == -1:
        return True
    try:
        front = yaml.safe_load(text[len(_FRONTMATTER_OPEN) : end])
    except yaml.YAMLError:
        return True
    if not isinstance(front, dict):
        return True
    # 空・null の paths が scoped 扱いになるかは未実測 (Issue #36 の probe は
    # 非空の値しか使っていない)。曖昧なので他のケースと同じく計上側へ倒す
    return not front.get("paths")


def always_loaded_bytes(repo_root: str) -> int:
    """常時ロードされる指示ファイルの合計バイト数を返す。"""
    root = Path(repo_root)
    total = 0

    claude_md = root / CLAUDE_MD_PATH
    if claude_md.is_file():
        total += len(claude_md.read_bytes())

    for rule in sorted(root.glob(RULES_GLOB)):
        text = rule.read_text(encoding="utf-8")
        if is_always_loaded_rule(text):
            total += len(text.encode("utf-8"))

    return total


def check_instruction_budget(repo_root: str) -> list[Finding]:
    """常時ロード層が予算を超えていないか検査する。"""
    actual = always_loaded_bytes(repo_root)
    if actual <= ALWAYS_LOADED_BUDGET_BYTES:
        return []
    over = actual - ALWAYS_LOADED_BUDGET_BYTES
    detail = f"{actual}B > {ALWAYS_LOADED_BUDGET_BYTES}B (超過 {over}B)"
    message = (
        "常時ロード層が予算を超えている。規範を references へ移すか paths 付き rules へ切り出すこと"
    )
    return [Finding(CLAUDE_MD_PATH, detail, message)]
