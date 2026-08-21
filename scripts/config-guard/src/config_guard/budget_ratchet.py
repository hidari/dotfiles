"""常時ロード層の予算定数が baseline から無音で増えていないことの検査。

`instruction_budget` の予算は上限を名乗るが、超えたときに上限のほうを書き換えれば
全緑で通る。実際に 1 セッションで 2 度上げている。追記が止まらないという起票理由
(実測値は `instruction_budget` の docstring) を防ぐ力が無いのはこの経路のためで、
爪の無い歯車になっていた。

上げること自体は禁じない。禁じるのは無音で上げることで、引き上げには
`BUDGET_RAISES` への記録 (日付・引き上げ後の値・理由) を要求する。据え置きと
引き下げは無条件に通す。

baseline は `BASELINE_REF` の同じファイルから読む。読み方の理由は `parse_budget`。
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

from config_guard.git_run import run_git_checked
from config_guard.models import Finding

BUDGET_NAME = "ALWAYS_LOADED_BUDGET_BYTES"
RAISES_NAME = "BUDGET_RAISES"
BUDGET_MODULE_PATH = "scripts/config-guard/src/config_guard/instruction_budget.py"

# 比較対象。main へ入った値より増えていないことを課すので、PR ブランチの親では
# なく main そのものを見る (親だと同じ PR 内の連続した引き上げが素通りする)。
BASELINE_REF = "origin/main"


def parse_budget(source: str) -> int | None:
    """Python ソースから module レベルの予算定数を読む。読めなければ None。

    ast を使うのは、regex だとコメントや文字列中の同名を拾い (定数名は docstring と
    Finding のメッセージにも出る)、exec だと baseline 側の任意コードを実行するため。
    module 直下の代入だけを見る。関数内のローカルは同名でも canonical ではない。

    値が整数でないときも None。壊れた baseline を 0 と読むと、どんな値に対しても
    「増えている」と報告する誤検出になる。
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets: list[ast.expr] = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue

        if not any(isinstance(t, ast.Name) and t.id == BUDGET_NAME for t in targets):
            continue
        # 受けたいのは整数リテラル 1 つなので、式を評価する literal_eval ではなく
        # ノードの形で判定する。注釈だけの宣言 (value が None) もここで落ちる
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, int):
            return value.value
        return None

    return None


def evaluate_ratchet(
    current: int, baseline: int, raises: tuple[tuple[str, int, str], ...]
) -> list[Finding]:
    """予算定数が baseline から増えていないか、増えているなら記録があるかを検査する。

    記録の 3 要素は互いに従属させずそれぞれ独立に報告する。1 つの検査を他の検査の
    内側へ入れると、外側を緩めた瞬間に内側が無言で vacuous になる。
    """
    if current <= baseline:
        return []

    over = current - baseline
    detail = f"{current}B > baseline {baseline}B (+{over}B)"
    if not raises:
        return [
            Finding(
                BUDGET_MODULE_PATH,
                detail,
                f"予算を上げるなら {RAISES_NAME} へ (日付, 引き上げ後の値, 理由) を 1 行足すこと。"
                "無音の引き上げは上限を上限でなくする",
            )
        ]

    raised_at, recorded, reason = raises[-1]
    findings: list[Finding] = []

    if recorded != current:
        findings.append(
            Finding(
                BUDGET_MODULE_PATH,
                f"{RAISES_NAME} の記録 {recorded}B != {BUDGET_NAME} {current}B",
                f"引き上げたら {RAISES_NAME} の末尾も同じ値にすること。"
                "食い違うと記録が実態を指さなくなる",
            )
        )
    if not reason.strip():
        findings.append(
            Finding(
                BUDGET_MODULE_PATH,
                f"{RAISES_NAME} の理由が空 ({detail})",
                "理由の無い記録は「上げた」以上の情報を持たない。何を足したのかを書くこと",
            )
        )
    try:
        date.fromisoformat(raised_at)
    except ValueError:
        findings.append(
            Finding(
                BUDGET_MODULE_PATH,
                f"{RAISES_NAME} の日付が読めない ({raised_at!r})",
                "日付が読めないと増加の傾向を後から測れない。ISO 8601 で書くこと",
            )
        )

    return findings


def check_budget_ratchet(
    repo_root: str,
    current: int,
    raises: tuple[tuple[str, int, str], ...],
    ref: str = BASELINE_REF,
) -> list[Finding]:
    """予算定数が baseline から無音で増えていないか検査する。

    予算モジュールを持たないリポジトリは対象外にする。`scan()` は任意のルートへ
    走るので、config-guard 自身を持たないリポジトリへ「baseline が取れない」と
    言っても意味がない。この early return はモジュールごと消したケースを見逃すが、
    そこは tests の `test_real_repo_has_the_budget_module` が実リポジトリで縛る。

    baseline が取れないときは Finding にする。skip すると検査が黙って無効になり、
    緑が「健全」と「そもそも見ていない」を区別しなくなる。
    """
    if not (Path(repo_root) / BUDGET_MODULE_PATH).is_file():
        return []

    try:
        source = run_git_checked(repo_root, "show", f"{ref}:{BUDGET_MODULE_PATH}")
    except RuntimeError:
        return [
            Finding(
                BUDGET_MODULE_PATH,
                f"baseline {ref} から取得できない",
                f"{ref} を fetch すること。CI の checkout は既定で PR の merge ref しか持たず、"
                "取れないまま通すとラチェットが黙って無効になる",
            )
        ]

    baseline = parse_budget(source)
    if baseline is None:
        return [
            Finding(
                BUDGET_MODULE_PATH,
                f"baseline {ref} 側に {BUDGET_NAME} が無い",
                f"定数を改名したなら {BUDGET_NAME} も追随させること。"
                "読めない baseline を 0 と読み替えると全ての値が「増えた」になる",
            )
        ]

    return evaluate_ratchet(current, baseline, raises)
