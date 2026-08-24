"""リポジトリをスキャンして構造逸脱を検出する。

stale なツール名参照 / committed settings.json の不変条件 / 追跡ファイルに変更を隠す index の
bit が立っていないか / apm.lock.yaml の deployed_files が gitignore されているか(新しい deploy
root の検出) / mise の global ツール pin が exact か / apm.yml の依存 pin が commit SHA で固定され
宣言どうしと実配置で揃っているか / herdr keybinding の方向整合と chord 重複 / 追跡下の
Markdown の相対リンクが実在するか / 常時ロードされる指示ファイルの総バイト数が予算内か /
その予算そのものが main から無音で上がっていないか / rules の paths 宣言が pin と
一致するか / 指示ファイルどうしの参照 (パスと見出し) が実在するか / rules が定義する語が
定義の届かない層で使われていないかを検査する。
"""

from __future__ import annotations

import glob
import sys
from pathlib import Path

from config_guard.apm_gitignore import check_apm_deployed_files_ignored
from config_guard.apm_pins import check_apm_pins
from config_guard.budget_ratchet import check_budget_ratchet
from config_guard.extractors import extract_skill_tokens
from config_guard.git_source import read_committed_settings
from config_guard.herdr_keys import check_herdr_keys, read_default_config
from config_guard.index_flags import check_index_flags
from config_guard.instruction_budget import (
    ALWAYS_LOADED_BUDGET_BYTES,
    BUDGET_RAISES,
    budget_summary,
    check_instruction_budget,
)
from config_guard.instruction_refs import check_instruction_refs
from config_guard.markdown_links import check_markdown_links
from config_guard.mise_pins import check_mise_pins
from config_guard.models import Finding
from config_guard.rules_paths import check_rules_paths
from config_guard.settings_invariants import check_settings_invariants
from config_guard.term_definitions import check_term_definitions
from config_guard.tool_refs import validate_tool_token

SKILLS_GLOB = "home/.claude/skills/*/SKILL.md"


def scan(repo_root: str) -> list[Finding]:
    """リポジトリ設定の不変条件を検査する(検査項目はモジュール docstring 参照)。"""
    root = Path(repo_root).resolve()
    findings: list[Finding] = []

    # skills の allowed-tools
    for skill_path in sorted(glob.glob(str(root / SKILLS_GLOB))):
        text = Path(skill_path).read_text(encoding="utf-8")
        rel = str(Path(skill_path).relative_to(root))
        for token in extract_skill_tokens(text):
            reason = validate_tool_token(token)
            if reason is not None:
                findings.append(Finding(rel, token, reason))

    # committed settings.json の不変条件（permissions のツール名検証を含む）
    settings = read_committed_settings(str(root))
    findings.extend(check_settings_invariants(settings))

    # 追跡ファイルに変更を隠す index の bit (skip-worktree / assume-unchanged) が
    # 立っていないか。立つと live 側の変更が git から見えず、CI が捕捉できない drift へ戻る
    findings.extend(check_index_flags(str(root)))

    # apm.lock.yaml の deployed_files が全て gitignore されているか（新しい deploy root の検出）
    findings.extend(check_apm_deployed_files_ignored(str(root)))

    # mise の global ツール pin が exact か（浮動 pin はマシン間で解決版がずれる）
    findings.extend(check_mise_pins(str(root)))

    # apm.yml の依存 pin が浮動せず同一リポジトリで揃っているか（1 行の更新漏れは
    # install が成功したまま、そのパッケージだけ古い版が配られる形で壊れる）
    findings.extend(check_apm_pins(str(root)))

    # herdr の keybinding: previous/next の方向整合と chord 重複。
    # アクション名の照合は herdr がある環境でのみ行う (CI には herdr が無いので skip される)。
    findings.extend(check_herdr_keys(str(root), read_default_config()))

    # 追跡下の Markdown の相対リンクが実在するか。Issue を closed/ へ移すと
    # 両端のリンクが切れるが、リンク元は変更されないため差分だけでは検出できない
    findings.extend(check_markdown_links(str(root)))

    # 常時ロードされる指示ファイルの総バイト数が予算内か。追記は止まらない
    # (実測は instruction_budget の docstring) ので、削減量ではなく上限を固定する
    findings.extend(check_instruction_budget(str(root)))

    # 予算定数そのものが main から無音で上がっていないか。超えたときに上限のほうを
    # 書き換えれば通る形だと、上の予算検査は上限として働かない (実際に 2 度上げている)
    findings.extend(check_budget_ratchet(str(root), ALWAYS_LOADED_BUDGET_BYTES, BUDGET_RAISES))

    # rules の paths 宣言が pin と一致するか。誤った paths は scoped と判定されて
    # 予算にも計上されないので、予算検査では捕まらない (全緑のままルールが沈黙する)
    findings.extend(check_rules_paths(str(root)))

    # 指示ファイルどうしの参照が実在するか。参照は全てバッククォート記法なので
    # markdown_links からは 1 件も見えない (インラインコードを除去してから探すため)
    findings.extend(check_instruction_refs(str(root)))

    # rules が定義する語が、定義の届かない層で使われていないか。移設は語だけを
    # 常時層へ残す形で壊れ、参照検査からも予算検査からも見えない
    findings.extend(check_term_definitions(str(root)))

    return findings


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    repo_root = args[0] if args else "."
    # 問題の有無に関わらず出す。移設で常時層が減ったことは「赤くならなかった」では
    # 見えず、scoped 層を併記しないと移設が「消えた」ように見えるメトリクスになる
    print(f"config-guard: {budget_summary(repo_root)}")
    findings = scan(repo_root)
    if not findings:
        print("config-guard: 問題は検出されませんでした")
        return 0
    for finding in findings:
        print(f"config-guard: {finding.source}: {finding.message} [{finding.detail}]")
    print(f"config-guard: {len(findings)} 件の問題を検出しました")
    return 1
