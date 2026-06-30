#!/usr/bin/env python3
"""Claude Code PreToolUse hook — runs tirith check on Bash tool calls.

Reads JSON from stdin (Claude Code hook protocol), extracts the command,
and delegates to `tirith check --json` for security analysis.

Exit codes:
  0 — hook completed successfully (decision in stdout JSON)
  Non-zero — hook error (fail-closed by default; set TIRITH_FAIL_OPEN=1 for fail-open)

Output (stdout):
  For deny:
    {"hookSpecificOutput": {"hookEventName": "PreToolUse",
      "permissionDecision": "deny", "permissionDecisionReason": "..."}}
  For warn-allow:
    {"hookSpecificOutput": {"hookEventName": "PreToolUse",
      "permissionDecision": "allow", "permissionDecisionReason": "...",
      "additionalContext": "..."}}

Fail policy:
  ほとんどのエラー経路（空/不正な stdin、timeout、想定外 exit code 等）は fail-closed
  （TIRITH_FAIL_OPEN=1 で fail-open に切替）。例外は「tirith バイナリ未検出」で、これは
  脅威検出ではなくインフラ未整備（tirith 未インストール）なので、User スコープで全プロジェクトに
  効く本フックがシェルを全死にさせないよう意図的に fail-open する。ただし TIRITH_BIN を明示
  指定したのにそのパスが存在しない場合は設定ミス（typo 等）とみなし fail-closed に倒す。

Environment:
  TIRITH_BIN              — path to tirith binary (default: "tirith")
  TIRITH_HOOK_WARN_ACTION — "allow" (default) or "deny"
  TIRITH_FAIL_OPEN        — "1" でエラー時 fail-open（既定は fail-closed）
  TIRITH_TIMEOUT          — tirith check のタイムアウト秒（既定 10、不正値は既定にフォールバック）
"""

import json
import os
import shutil
import subprocess
import sys

# tirith check のタイムアウト秒（既定値）。
DEFAULT_TIMEOUT = 10.0


def get(data: dict[str, object], *keys: str) -> object | None:
    """Return the first matching key from data (supports dual-case fields)."""
    for k in keys:
        if k in data:
            return data[k]
    return None


def _resolve_tirith_bin() -> str:
    """tirith バイナリのパスを解決する: TIRITH_BIN → PATH → mise shim (home 相対)。
    どれも無ければ "tirith" を返す（subprocess が FileNotFoundError を投げ fail-open）。
    machine 固有パスを settings に焼かず .py 側で実行時解決する（全プロジェクト共有のため）。"""
    mise_shim = os.path.expanduser("~/.local/share/mise/shims/tirith")
    return (
        os.environ.get("TIRITH_BIN")
        or shutil.which("tirith")
        or (mise_shim if os.path.exists(mise_shim) else None)
        or "tirith"
    )


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


def deny(reason: str) -> None:
    """Print a deny decision using hookSpecificOutput and exit 0."""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


def fail_action() -> str:
    """Return the fail action: deny (default, fail-closed) or allow (fail-open via env)."""
    return "allow" if os.environ.get("TIRITH_FAIL_OPEN") == "1" else "deny"


def fail_closed(reason: str) -> None:
    """Deny or allow based on TIRITH_FAIL_OPEN, for error/missing-binary paths."""
    action = fail_action()
    if action == "deny":
        deny(reason)
    else:
        sys.exit(0)


def _hook_event(event: str, detail: str | None = None) -> None:
    """Log a hook telemetry event via tirith hook-event (fire-and-forget)."""
    tirith_bin = _resolve_tirith_bin()
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
    """Extract finding titles from tirith JSON output into a human-readable string.

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
        if not raw.strip():
            # Empty input — cannot determine command, fail-closed
            fail_closed("tirith: empty hook input — blocked for safety")
            return
        data = json.loads(raw)
    except (json.JSONDecodeError, OSError):
        _hook_event("parse_error")
        fail_closed("tirith: failed to parse hook input — blocked for safety")
        return

    if not isinstance(data, dict):
        fail_closed("tirith: invalid hook input format — blocked for safety")
        return

    # Dual-case field extraction (camelCase and snake_case)
    event = get(data, "hook_event_name", "hookEventName")
    tool = get(data, "tool_name", "toolName")
    tool_input = get(data, "tool_input", "toolInput") or {}

    # Only intercept PreToolUse + Bash
    if event != "PreToolUse" or tool != "Bash":
        sys.exit(0)

    if not isinstance(tool_input, dict):
        fail_closed("tirith: invalid tool_input format — blocked for safety")
        return

    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        fail_closed("tirith: no command found in hook input — blocked for safety")
        return

    # Locate tirith binary
    tirith_bin = _resolve_tirith_bin()

    env = os.environ.copy()
    env["TIRITH_INTEGRATION"] = "claude-code"

    try:
        result = subprocess.run(
            [
                tirith_bin,
                "check",
                "--json",
                "--non-interactive",
                "--shell",
                "posix",
                "--",
                command,
            ],
            capture_output=True,
            text=True,
            timeout=_timeout_seconds(),
            env=env,
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
            return
        # TIRITH_BIN 未指定での未検出は tirith 未インストール = インフラ未整備。User スコープで
        # 全プロジェクトに効くため、ここだけ意図的に fail-open し、tirith 不在がシェルを全死に
        # させないようにする（docstring の Fail policy 参照）。
        print(
            f"tirith: {tirith_bin} not found — skipping check (install tirith to re-enable)",
            file=sys.stderr,
        )
        sys.exit(0)
    except subprocess.TimeoutExpired:
        _hook_event("timeout")
        fail_closed("tirith: check timed out — blocked for safety")
        return
    except OSError as e:
        _hook_event("unexpected_exit", str(e))
        fail_closed(f"tirith: OS error running check — {e}")
        return

    # Unexpected exit code — fail-closed
    if result.returncode not in (0, 1, 2):
        _hook_event("unexpected_exit", f"exit code {result.returncode}")
        fail_closed(f"tirith: unexpected exit code {result.returncode} — blocked for safety")
        return
    if result.returncode != 0 and not result.stdout.strip():
        _hook_event("unexpected_exit", f"exit code {result.returncode} with no output")
        fail_closed("tirith: check returned non-zero with no output — blocked for safety")
        return

    # Exit 0 = clean, allow
    if result.returncode == 0:
        _hook_event("check_ok")
        sys.exit(0)

    # Exit 2 = warn — check TIRITH_HOOK_WARN_ACTION
    if result.returncode == 2:
        warn_action = os.environ.get("TIRITH_HOOK_WARN_ACTION", "allow").lower()
        if warn_action not in ("allow", "deny"):
            print(
                f"tirith: warning: unrecognized TIRITH_HOOK_WARN_ACTION='{warn_action}', "
                "defaulting to 'allow'",
                file=sys.stderr,
            )
            warn_action = "allow"
        if warn_action != "deny":
            _hook_event("warn_allowed")
            warning_text = _build_warning_text(result.stdout)
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "allow",
                            "permissionDecisionReason": warning_text,
                            "additionalContext": warning_text,
                        }
                    }
                )
            )
            sys.exit(0)

    # Exit 1 = block, Exit 2 + deny = block
    if result.returncode == 1:
        _hook_event("check_block")
    else:
        _hook_event("warn_denied")
    reason = _build_warning_text(result.stdout)
    deny(reason)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Fail-closed on unexpected errors (respects TIRITH_FAIL_OPEN)
        if os.environ.get("TIRITH_FAIL_OPEN") == "1":
            sys.exit(0)
        # Deny — print structured output so Claude Code shows a message
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": (
                            "tirith: unexpected hook error — blocked for safety"
                        ),
                    }
                }
            )
        )
        sys.exit(0)
