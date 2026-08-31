#!/usr/bin/env python3
"""Claude Code の PreToolUse フック — Bash ツール呼び出しを tirith で検査する。

stdin から hook JSON（Claude Code hook プロトコル）を読み、command を取り出して
`tirith check --json` に委譲しセキュリティ解析する。

Exit code:
  0     — フックは正常終了（判定は stdout の JSON に入る）
  非 0  — フックエラー（既定は fail-closed。TIRITH_FAIL_OPEN=1 で fail-open）

出力（stdout）:
  deny の場合:
    {"hookSpecificOutput": {"hookEventName": "PreToolUse",
      "permissionDecision": "deny", "permissionDecisionReason": "..."}}
  warn とバイナリ未検出の場合（判定を出さず文脈だけ載せる）:
    {"hookSpecificOutput": {"hookEventName": "PreToolUse",
      "additionalContext": "..."}}

  allow は出さない。この層は tirith のパーサの射程までしか見ておらず、包み込み
  (bash -c '...' / バッククォート / eval '...') の中身は tirith が解析しないため素通りする
  (実測)。完全になれない検査層が許可を出すと、その許可が permission プロンプトを飛ばし、
  「検査が何か言った」ことが「検査を省く」に化ける。差し控えることだけができる。

Fail ポリシー:
  ほとんどのエラー経路（空/不正な stdin、timeout、想定外 exit code 等）は fail-closed
  （TIRITH_FAIL_OPEN=1 で fail-open に切替）。例外は「tirith バイナリ未検出」で、これは
  脅威検出ではなくインフラ未整備（tirith 未インストール）なので、User スコープで全プロジェクトに
  効く本フックがシェルを全死にさせないよう意図的に fail-open する。ただし TIRITH_BIN を明示
  指定したのにそのパスが存在しない場合は設定ミス（typo 等）とみなし fail-closed に倒す。

環境変数（いずれもフック自身が読む。tirith の子プロセスへは TIRITH_ 接頭辞を渡さない）:
  TIRITH_BIN              — tirith バイナリのパス（既定: "tirith"）
  TIRITH_FAIL_OPEN        — "1" でエラー時 fail-open（既定は fail-closed）
  TIRITH_TIMEOUT          — tirith check のタイムアウト秒（既定 10、不正値は既定にフォールバック）
"""

import json
import os
import subprocess
import sys
from typing import NoReturn

import guard_resolve
import pretooluse

# tirith check のタイムアウト秒（既定値）。
DEFAULT_TIMEOUT = 10.0

# tirith の子プロセスへ渡す環境と argv の組み立ては guard_resolve.tirith_child_env /
# tirith_check_argv が持つ。probe_tirith と同じフラグ・同じ環境で呼ぶことを保証するためで、
# フック自身が読む変数（TIRITH_BIN / TIRITH_FAIL_OPEN / TIRITH_TIMEOUT）は os.environ から
# 直接読むためこのフィルタの対象外である。

# 入力を解釈できなかったときの deny 理由。共有層は理由を problem で返すだけで文面を持たない。
# 倒し方（このフックは環境変数の逃げ道つき fail-closed）と併せてフック側の判断だからである。
_INPUT_PROBLEM_REASONS: dict[pretooluse.InputProblem, str] = {
    pretooluse.InputProblem.EMPTY: "tirith: empty hook input — blocked for safety",
    pretooluse.InputProblem.MALFORMED_JSON: (
        "tirith: failed to parse hook input — blocked for safety"
    ),
    pretooluse.InputProblem.NOT_OBJECT: "tirith: invalid hook input format — blocked for safety",
    pretooluse.InputProblem.TOOL_INPUT_NOT_OBJECT: (
        "tirith: invalid tool_input format — blocked for safety"
    ),
    pretooluse.InputProblem.NO_COMMAND: (
        "tirith: no command found in hook input — blocked for safety"
    ),
}


def _timeout_seconds() -> float:
    """TIRITH_TIMEOUT を秒として解釈する。未設定/不正値/非正値は既定値にフォールバック。"""
    raw = os.environ.get("TIRITH_TIMEOUT")
    if raw is None:
        return DEFAULT_TIMEOUT
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT
    return value if value > 0 else DEFAULT_TIMEOUT


def deny(reason: str) -> NoReturn:
    """hookSpecificOutput で deny 判定を出力して exit 0 する。"""
    print(pretooluse.decision_payload("deny", reason))
    sys.exit(0)


def fail_closed(reason: str) -> NoReturn:
    """エラー/バイナリ不在経路の fail-closed。TIRITH_FAIL_OPEN=1 のときだけ allow(exit 0)。"""
    if os.environ.get("TIRITH_FAIL_OPEN") == "1":
        sys.exit(0)
    deny(reason)


def _hook_event(event: str, detail: str | None = None) -> None:
    """tirith hook-event でフックのテレメトリイベントを記録する（fire-and-forget）。"""
    tirith_bin = guard_resolve.resolve_tirith_bin()
    try:
        cmd = [
            tirith_bin,
            "hook-event",
            "--integration",
            "claude-code",
            "--hook-type",
            "pre_tool_use",
            "--event",
            event,
        ]
        if detail:
            cmd.extend(["--detail", detail])
        # fire-and-forget。親フックの stdin/出力を継承せず、独立セッションで detach する。
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def _build_warning_text(stdout: str) -> str:
    """tirith の JSON 出力から finding のタイトルを抽出し、人間可読な文字列にする。

    tirith が --json 契約から外れた出力（非オブジェクト、findings が dict 配列でない等）を返しても
    例外で decision 経路を落とさず、生テキストの reason に degrade する（isinstance で防御）。"""
    if not (stdout and stdout.strip()):
        return "Tirith security check failed"
    try:
        verdict = json.loads(stdout)
    except json.JSONDecodeError:
        return stdout.strip()[:500]
    findings = verdict.get("findings") if isinstance(verdict, dict) else None
    if not isinstance(findings, list):
        # オブジェクトでない / findings が配列でない = 想定外の構造。生テキストに退避する。
        return stdout.strip()[:500]
    parts: list[str] = []
    for f in findings:
        if not isinstance(f, dict):
            continue
        title = f.get("title", f.get("rule_id", "unknown"))
        severity = f.get("severity", "")
        parts.append(f"[{severity}] {title}" if severity else f"{title}")
    if not parts:
        return "Tirith security check failed"
    return "Tirith: " + "; ".join(parts)


def main() -> None:
    try:
        raw = sys.stdin.read()
    except OSError:
        # 読み取り自体の失敗も「入力を解釈できなかった」として、JSON 破損と同じ理由文で倒す。
        # フックの利用者にとって stdin が読めないのと壊れているのとで対処が変わらないため。
        _hook_event("parse_error")
        fail_closed(_INPUT_PROBLEM_REASONS[pretooluse.InputProblem.MALFORMED_JSON])

    try:
        command = pretooluse.bash_command(pretooluse.parse_payload(raw))
    except pretooluse.HookInputError as exc:
        # テレメトリは JSON として壊れていた場合だけ打つ。空入力や型違いは呼び出し側の形の
        # 問題であって tirith の解析失敗ではないので、parse_error として数えない。
        if exc.problem is pretooluse.InputProblem.MALFORMED_JSON:
            _hook_event("parse_error")
        fail_closed(_INPUT_PROBLEM_REASONS[exc.problem])

    # PreToolUse + Bash 以外は判定を出さずに素通りさせる
    if command is None:
        sys.exit(0)

    tirith_bin = guard_resolve.resolve_tirith_bin()

    try:
        result = subprocess.run(
            guard_resolve.tirith_check_argv(tirith_bin, command),
            capture_output=True,
            text=True,
            timeout=_timeout_seconds(),
            env=guard_resolve.tirith_child_env(),
        )
    except FileNotFoundError:
        # TIRITH_BIN を明示したのにパス不在 = 設定ミス（typo 等）。インフラ未整備ではなく
        # 誤設定なので、セキュリティ検査の無音バイパスを避けるため fail_closed に倒す。
        if os.environ.get("TIRITH_BIN"):
            _hook_event("binary_missing", "TIRITH_BIN path does not exist")
            fail_closed(
                f"tirith: TIRITH_BIN={tirith_bin} not found — blocked for safety "
                "(fix the path or unset TIRITH_BIN)"
            )
        # TIRITH_BIN 未指定での未検出は tirith 未インストール = インフラ未整備。User スコープで
        # 全プロジェクトに効くため、ここだけ意図的に fail-open し、tirith 不在がシェルを全死に
        # させないようにする（docstring の Fail ポリシー参照）。
        # stderr だけだと、検査が沈黙したことがモデルの文脈へ入らない。判定は出さずに
        # 文脈だけ載せる。ここで tirith のテレメトリは使えない（tirith 自体が不在なので
        # Popen が FileNotFoundError で失敗し、_hook_event が握り潰す）。
        # 「tirith が入っていない」はセッション単位の事実だが、ここはコマンド単位で告げる
        # ため同じ文が積み上がる。SessionStart 側の guard-health.py がセッション頭で
        # 1 回だけ告げる層を持つが、ここでの逐次通知は意図して残している。その 1 回で
        # 足りるかは実運用でセッションをまたぐまで判断できず、先に畳んでから足りないと
        # 分かると「セッション頭で見落とした」を後から復元する形になって高くつくためである。
        notice = (
            f"tirith: {tirith_bin} が見つからないため、このコマンドは検査されていません。"
            "以降のコマンドも同じ状態です。brew install tirith で検査が戻ります。"
        )
        print(notice, file=sys.stderr)
        print(pretooluse.notice_payload(notice))
        sys.exit(0)
    except subprocess.TimeoutExpired:
        _hook_event("timeout")
        fail_closed("tirith: check timed out — blocked for safety")
    except OSError as e:
        _hook_event("unexpected_exit", str(e))
        fail_closed(f"tirith: OS error running check — {e}")

    # 想定外の exit code は fail-closed
    if result.returncode not in (0, 1, 2):
        _hook_event("unexpected_exit", f"exit code {result.returncode}")
        fail_closed(f"tirith: unexpected exit code {result.returncode} — blocked for safety")
    if result.returncode != 0 and not result.stdout.strip():
        _hook_event("unexpected_exit", f"exit code {result.returncode} with no output")
        fail_closed("tirith: check returned non-zero with no output — blocked for safety")

    # exit 0 = clean。許可する
    if result.returncode == 0:
        _hook_event("check_ok")
        sys.exit(0)

    # exit 2 = warn。判定は出さず、警告文だけを文脈へ載せる。
    #
    # ここで permissionDecision: "allow" を出してはならない。allow は permission プロンプトを
    # 飛ばすため、tirith が「怪しい」と判断したコマンドの方が、何も言わなかったコマンド
    # （無出力の exit 0 = 通常の権限フローへ）より弱い審査で通ることになる。warn は稀ではなく、
    # finding の最大 severity が MEDIUM のときに返る（実測で 30 検体中 23 件）。
    #
    # ただし差し控えは「審査を強める」ことではない。settings.json の permissions.allow に
    # 載っているコマンドでは、判定を出さないことがそのまま自動承認になる。強めるには ask が
    # 要るが、warn の頻度からすると通知が過大になるため採っていない。
    #
    # 判定の強さを選べるノブは置かない。severity の閾値を動かしたいときは tirith 側の
    # policy を使う。
    if result.returncode == 2:
        _hook_event("warn_noticed")
        print(pretooluse.notice_payload(_build_warning_text(result.stdout)))
        sys.exit(0)

    # exit 1 = block
    _hook_event("check_block")
    deny(_build_warning_text(result.stdout))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # 想定外エラーは fail-closed（TIRITH_FAIL_OPEN=1 のときのみ fail-open）
        fail_closed("tirith: unexpected hook error — blocked for safety")
