"""常時ロードされる指示ファイルの総バイト数を予算内に保つ検査。

CLAUDE.md は追記で膨らみ続ける (実測: 2026-08-12 の 36,599B から 9 日で 52,766B)。
一回きりの削減は数週間で食われるため、削減量ではなく上限を検査で固定する。

「常時ロード」の判定は Claude Code の実測仕様に従う。

- User スコープの CLAUDE.md は session_start で必ずロードされる
- `~/.claude/rules/*.md` は paths frontmatter が無いときだけ session_start でロードされる
- paths を持つ rules は該当パターンのファイルを Read したときだけロードされる。
  予算には計上しないが無料ではなく、一致ファイルを読んだ agent 文脈ごとに払う (実測は Issue #36)

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
ALWAYS_LOADED_BUDGET_BYTES = 29223

# 予算を引き上げた記録。上げるときは (日付, 引き上げ後の値, 理由) を末尾へ 1 行足す。
# 許可の条件は budget_ratchet.evaluate_ratchet が canonical。
BUDGET_RAISES: tuple[tuple[str, int, str], ...] = (
    (
        "2026-08-24",
        29223,
        "Private と Public のリポジトリが混在するため公開範囲を常に確認する規範を 前提 へ追加し、"
        "開発スタイルの主語を 私 から ユーザー (Hidari) へ明確化した (+211B)。"
        "規範側は過去の露出インシデントに直結するので常時層に置く必要がある。"
        "体系的な削減は Issue #36 の 本体に残す核を確定する で行う",
    ),
)

CLAUDE_MD_PATH = "home/.claude/CLAUDE.md"
RULES_GLOB = "home/.claude/rules/*.md"

_FRONTMATTER_OPEN = "---\n"

_H2_PREFIX = "## "
_PREAMBLE_NAME = "(冒頭)"

# 超過時に名指しするカテゴリの数。全件出すと報告が読まれなくなる。
_HEAVIEST_SHOWN = 3


def rule_files(repo_root: str) -> dict[str, str]:
    """`RULES_GLOB` に一致する rules を {ファイル名: 本文} で返す。

    追跡状態は見ない。予算の実態も Claude Code の発火もファイルシステム上の実体で
    決まるので、git の index を挟むと対象がずれる。列挙をここに 1 つだけ置くのは、
    予算検査と paths 検査が別の規約で別の集合を見たまま両方緑になるのを防ぐため。
    """
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(Path(repo_root).glob(RULES_GLOB))}


def rule_paths(text: str) -> object:
    """rules の frontmatter が宣言する paths を、YAML が読んだままの形で返す。

    frontmatter は YAML として解釈する。regex で `paths:` を探すと本文中の記述を
    frontmatter と誤読し、正当な scoped rules を予算へ計上してしまう。

    frontmatter が無い・壊れているときは None。`paths` が空リストや null のときは
    その値をそのまま返す (呼び出し側は非空かどうかで判定する)。型も検証せず、
    `paths: "x"` のような不正な形も値として返す。形の pin は rules_paths が持つ。
    """
    if not text.startswith(_FRONTMATTER_OPEN):
        return None
    end = text.find("\n---", len(_FRONTMATTER_OPEN) - 1)
    if end == -1:
        return None
    try:
        front = yaml.safe_load(text[len(_FRONTMATTER_OPEN) : end])
    except yaml.YAMLError:
        return None
    if not isinstance(front, dict):
        return None
    return front.get("paths")


def is_always_loaded_rule(text: str) -> bool:
    """rules の本文が paths frontmatter を持たない (= 常時ロードされる) かを返す。

    frontmatter が壊れているときは常時ロード扱い (予算へ計上) にする。
    計上漏れは予算を無言ですり抜けるので、誤るなら厳しい側へ倒す。

    空・null の paths が Claude Code 側で scoped 扱いになるかは未実測 (Issue #36 の
    probe は非空の値しか使っていない)。曖昧なので他のケースと同じく計上側へ倒す。
    """
    return not rule_paths(text)


def always_loaded_bytes(repo_root: str) -> int:
    """常時ロードされる指示ファイルの合計バイト数を返す。"""
    root = Path(repo_root)
    total = 0

    claude_md = root / CLAUDE_MD_PATH
    if claude_md.is_file():
        total += len(claude_md.read_bytes())

    for text in rule_files(repo_root).values():
        if is_always_loaded_rule(text):
            total += len(text.encode("utf-8"))

    return total


def category_bytes(text: str) -> list[tuple[str, int]]:
    """本文を H2 見出しで区切り、(見出し, バイト数) を重い順に返す。

    粒度をカテゴリ (H2) に留めるのは、H3 まで割ると件数が読める量を超えるため。
    最初の見出しより前も 1 件として数える。落とすと冒頭の分がどこにも現れず、
    「ここに挙がっていない分は無い」と読めてしまう。

    区切りの改行は前のセクションから外れるので、合計はファイルサイズと一致しない
    (見出しの数だけ小さい)。どこが重いかを示す用途なので、その差は許容する。
    """
    sections: list[tuple[str, list[str]]] = [(_PREAMBLE_NAME, [])]

    for line in text.split("\n"):
        if line.startswith(_H2_PREFIX):
            sections.append((line[len(_H2_PREFIX) :], [line]))
        else:
            sections[-1][1].append(line)

    sized = [(name, len("\n".join(ls).encode("utf-8"))) for name, ls in sections if ls]
    return sorted(sized, key=lambda entry: entry[1], reverse=True)


def check_instruction_budget(repo_root: str) -> list[Finding]:
    """常時ロード層が予算を超えていないか検査する。

    超過量だけでは「どこを削るか」が分からず、報告が行動につながらない
    (定数を上げる方が早いという判断を誘う)。重いカテゴリを名指しする。
    """
    actual = always_loaded_bytes(repo_root)
    if actual <= ALWAYS_LOADED_BUDGET_BYTES:
        return []

    over = actual - ALWAYS_LOADED_BUDGET_BYTES
    detail = f"{actual}B > {ALWAYS_LOADED_BUDGET_BYTES}B (超過 {over}B)"
    message = (
        "常時ロード層が予算を超えている。規範を references へ移すか paths 付き rules へ切り出すこと"
    )

    claude_md = Path(repo_root) / CLAUDE_MD_PATH
    if claude_md.is_file():
        heaviest = category_bytes(claude_md.read_text(encoding="utf-8"))[:_HEAVIEST_SHOWN]
        message += "。重い順: " + " / ".join(f"{name} {size}B" for name, size in heaviest)

    return [Finding(CLAUDE_MD_PATH, detail, message)]


def budget_summary(repo_root: str) -> str:
    """常時層と scoped 層の現況を 1 行で返す。

    scoped 層も出すのは、移設した分が数字の上で「消えた」ように見えるため。
    移設は無料ではなく、一致ファイルを読んだ agent 文脈ごとに払っている。
    片側だけを見ていると「移せば必ず勝ち」というメトリクスのままになる。
    """
    scoped = [text for text in rule_files(repo_root).values() if not is_always_loaded_rule(text)]
    scoped_bytes = sum(len(text.encode("utf-8")) for text in scoped)
    return (
        f"常時 {always_loaded_bytes(repo_root)}B / 予算 {ALWAYS_LOADED_BUDGET_BYTES}B、"
        f"scoped {len(scoped)} 枚 {scoped_bytes}B"
    )
