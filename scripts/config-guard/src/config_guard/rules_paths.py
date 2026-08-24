"""`home/.claude/rules/*.md` の paths 宣言が pin と一致するかの検査。

paths を「非空だが誤った値」にしても `is_always_loaded_rule` は scoped と判定し、
`instruction_budget` は予算へ計上しない。つまり既存のどの検査も赤くならないまま
ルールが永久に沈黙する。リストの編集を可視化するのがこの検査の役目。

glob の意味論は検証しない。どのパスが一致するかを決めるのは Claude Code のマッチャで、
その挙動は実プローブでしか測れない。Python 標準の glob 実装を借りても代わりにはならず、
自前の翻訳器を置けば翻訳器を pin するだけになる (実マッチャと意味がずれても両方緑で通る)。
実マッチャの検証は Issue #36 の live probe が持ち、ここはリストの編集だけを見る。

`cli.scan()` へ載せてあるのは、pre-commit の `config-guard-scan` が `always_run: true` で
毎コミット発火するため。`files` 方式のフックへ載せると、守る対象である rules だけを
編集したコミットで無音になる (同じ穴は tests/test_precommit_wiring.py が別途 pin している)。
"""

from __future__ import annotations

from pathlib import Path

from config_guard.instruction_budget import RULES_GLOB, rule_files, rule_paths
from config_guard.models import Finding

_RULES_DIR = RULES_GLOB.rsplit("/", 1)[0]

# 各 rules が宣言する paths。測定の詳細は Issue #36 の「paths は測ってから決めた」節と
# 「corpus 問題を数字で決着させた」節。前者が 8 パターン時代、後者が testing の現在のリスト。
# markdown の 1 パターンは「Markdown の規範を scoped へ移した」節が持つ。
EXPECTED_PATHS: dict[str, list[str]] = {
    "frontend-practices.md": [
        "**/*.tsx",
        "**/*.jsx",
        "**/*.html",
        "**/*.css",
    ],
    "markdown-practices.md": [
        "**/*.md",
    ],
    "testing-practices.md": [
        "**/*.test.*",
        "**/*.spec.*",
        "**/*_test.*",
        "**/*-test.*",
        "**/test_*.*",
        "**/*.Tests.ps1",
        "**/tests/**",
        "**/test/**",
        "**/__tests__/**",
        "**/test-utils/**",
        "**/*.rs",
    ],
}

# 候補に挙がったが載せないと決めたパターンと、その理由。理由ごと pin しないと、
# 次に見た人が「漏れている」と判断して足し直す。件数は書かない (リポジトリごとに
# 違う数字を literal で持つと、手元で裏取りした人には偽に見える)。
DELIBERATELY_EXCLUDED: dict[str, str] = {
    "**/spec/**": (
        "テストではなく仕様の置き場だった (測定は Issue #36 の「paths は測ってから決めた」節)"
    ),
    "**/specs/**": (
        "**/spec/** と同じ。実体はほぼ全件が設計ドキュメントなので、一致が偽陽性にしかならない"
    ),
    "**/*.bats": "すべて tests/ 配下にあり **/tests/** が拾うので限界カバレッジが 0",
    "**/*test*": "substring 形。Issue や設計ドキュメントの .md を大量に巻き込み、測って除外した "
    "**/specs/** と同じ失敗を作り直す (測定は Issue #36 の「corpus 問題を数字で決着させた」節)",
    "**/*spec*": "substring 形。**/*test* と同じ理由で載せない",
    "**/*_spec.rb": "RSpec の規約。管理下のリポジトリに実体が無く限界カバレッジが 0 なので、実際に"
    "使い始めてから測って足す (測定は Issue #36 の「corpus 問題を数字で決着させた」節)",
    "**/*.feature": "Cucumber の規約。**/*_spec.rb と同じく管理下に実体が無く限界カバレッジが 0",
    "**/*.mdx": "MDX の拡張子。管理下に実体が無く限界カバレッジが 0 なので、**/*_spec.rb と"
    "同じ扱いで実際に使い始めてから測って足す",
}


def check_rules_paths(repo_root: str) -> list[Finding]:
    """rules の paths 宣言が pin と一致するかを検査する。

    rules ディレクトリが無いリポジトリは対象外にする。`scan()` は任意のルートへ対して
    走るので、rules を管理していないリポジトリへ「pin したファイルが無い」と言っても
    意味がない。この early return はディレクトリごと消したケースを見逃すが、そこは
    tests の `test_real_repo_has_a_rules_dir` が実リポジトリに対して縛る。
    """
    if not (Path(repo_root) / _RULES_DIR).is_dir():
        return []

    findings: list[Finding] = []
    actual = rule_files(repo_root)

    for name in sorted(set(actual) - set(EXPECTED_PATHS)):
        findings.append(
            Finding(
                f"{_RULES_DIR}/{name}",
                "pin が無い",
                f"rules を足したら {__name__} の EXPECTED_PATHS へも足すこと。"
                "pin の無い rules は paths が壊れても誰も気づかない",
            )
        )
    for name in sorted(set(EXPECTED_PATHS) - set(actual)):
        findings.append(
            Finding(
                f"{_RULES_DIR}/{name}",
                "実体が無い",
                f"rules を消したら {__name__} の EXPECTED_PATHS からも消すこと",
            )
        )

    for name in sorted(set(actual) & set(EXPECTED_PATHS)):
        declared = rule_paths(actual[name])
        expected = EXPECTED_PATHS[name]
        if declared != expected:
            findings.append(
                Finding(
                    f"{_RULES_DIR}/{name}",
                    f"{declared!r} != {expected!r}",
                    "paths が pin と違う。意図した変更なら pin も更新し、"
                    "実マッチャで発火することを実プローブで確かめること",
                )
            )
        # pin と実体が食い違っていても、除外したパターンの混入は独立に報告する。
        # 上の比較に依存させると、比較を緩めた瞬間にこちらが無言で vacuous になる
        declared_globs = declared if isinstance(declared, list) else []
        for glob, reason in sorted(DELIBERATELY_EXCLUDED.items()):
            if glob in declared_globs:
                findings.append(
                    Finding(
                        f"{_RULES_DIR}/{name}",
                        glob,
                        f"載せないと決めたパターンが入っている。理由: {reason}",
                    )
                )

    return findings
