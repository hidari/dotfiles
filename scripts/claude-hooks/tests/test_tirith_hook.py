"""tirith-check.py（Claude Code PreToolUse/Bash フック）の黒箱統合テスト。

フックを subprocess 起動し、stdin に hook JSON を、TIRITH_BIN に偽 tirith スクリプトを与えて
stdout(decision JSON) と exit code を exact 検証する。モックは使わず、exit 0/1/2・timeout・
非JSON出力・バイナリ不在の各分岐を実 subprocess 経由で再現する（CLAUDE.md: モック回避）。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from conftest import HOOKS_DIR

HOOK = HOOKS_DIR / "tirith-check.py"

# 偽 tirith が返す JSON。findings は rule_id / title / severity を持つ（本物の schema と同形）。
_BLOCK_FINDING = {"rule_id": "blast", "title": "dangerous rm", "severity": "HIGH"}
_WARN_FINDING = {"rule_id": "url_ip", "title": "suspicious URL", "severity": "MEDIUM"}
ALLOW_JSON = json.dumps({"action": "allow", "findings": []})
BLOCK_JSON = json.dumps({"action": "block", "findings": [_BLOCK_FINDING]})
WARN_JSON = json.dumps({"action": "warn", "findings": [_WARN_FINDING]})


def make_fake_tirith(
    directory: Path, *, stdout: str = "", exit_code: int = 0, sleep: float = 0.0
) -> Path:
    """指定の stdout / exit code / sleep を持つ偽 tirith 実行可能スクリプトを生成して返す。
    ARG_LOG 環境変数が設定されていれば受領した argv を 1 行 1 引数で書き出す（argv 検証用）。"""
    script = directory / "fake-tirith.sh"
    # ARG_LOG は check サブコマンドの argv のみ記録する。fire-and-forget な hook-event 呼び出しが
    # 同じファイルを上書きして check の argv を消す race を避ける（CI で顕在化した）。
    lines = [
        "#!/bin/sh",
        '[ "$1" = check ] && [ -n "$ARG_LOG" ] && printf \'%s\\n\' "$@" > "$ARG_LOG"',
    ]
    if sleep:
        lines.append(f"sleep {sleep}")
    if stdout:
        safe = stdout.replace("'", "'\\''")
        lines.append(f"printf '%s' '{safe}'")
    lines.append(f"exit {exit_code}")
    script.write_text("\n".join(lines) + "\n")
    script.chmod(0o755)
    return script


def run_hook(
    hook_input: Mapping[str, object] | str | None,
    *,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """フックを subprocess 起動する。基底環境から TIRITH_* を除去し extra_env のみ適用する。"""
    env = {k: v for k, v in os.environ.items() if not k.startswith("TIRITH_")}
    if extra_env:
        env.update(extra_env)
    if hook_input is None:
        raw = ""
    elif isinstance(hook_input, str):
        raw = hook_input
    else:
        raw = json.dumps(hook_input)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=raw,
        capture_output=True,
        text=True,
        env=env,
    )


def bash_input(command: str = "echo hi", *, camel: bool = False) -> dict[str, object]:
    """PreToolUse/Bash の hook 入力を作る。camel=True で camelCase フィールドにする。"""
    if camel:
        return {
            "hookEventName": "PreToolUse",
            "toolName": "Bash",
            "toolInput": {"command": command},
        }
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def _hook_specific(proc: subprocess.CompletedProcess[str]) -> dict[str, object]:
    """stdout の hookSpecificOutput を返す。stdout が空（allow/passthrough）なら {}。"""
    out = proc.stdout.strip()
    if not out:
        return {}
    data = json.loads(out)
    assert isinstance(data, dict)
    hso = data.get("hookSpecificOutput")
    assert isinstance(hso, dict)
    return hso


def permission(proc: subprocess.CompletedProcess[str]) -> str | None:
    """permissionDecision を返す。stdout 無し（allow）なら None。"""
    hso = _hook_specific(proc)
    val = hso.get("permissionDecision")
    return val if isinstance(val, str) else None


def reason_text(proc: subprocess.CompletedProcess[str]) -> str:
    hso = _hook_specific(proc)
    val = hso.get("permissionDecisionReason")
    return val if isinstance(val, str) else ""


def context_text(proc: subprocess.CompletedProcess[str]) -> str:
    hso = _hook_specific(proc)
    val = hso.get("additionalContext")
    return val if isinstance(val, str) else ""


# ---------------------------------------------------------------------------
# 正常系: exit 0/1/2 のマッピング
# ---------------------------------------------------------------------------


def test_clean_command_allows_silently(tmp_path: Path) -> None:
    fake = make_fake_tirith(tmp_path, stdout=ALLOW_JSON, exit_code=0)
    proc = run_hook(bash_input("ls -la"), extra_env={"TIRITH_BIN": str(fake)})
    # allow は stdout を出さず exit 0（フックは何も注入しない）。
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_block_denies_with_finding_title(tmp_path: Path) -> None:
    fake = make_fake_tirith(tmp_path, stdout=BLOCK_JSON, exit_code=1)
    proc = run_hook(bash_input("rm -rf /"), extra_env={"TIRITH_BIN": str(fake)})
    assert proc.returncode == 0
    assert permission(proc) == "deny"
    assert "dangerous rm" in reason_text(proc)


def test_japanese_reason_is_emitted_unescaped(tmp_path: Path) -> None:
    """日本語の finding タイトルを \\uXXXX へ潰さず生のまま出す（ログでそのまま読むため）。

    偽 tirith 側が ensure_ascii でエスケープして返しても、フックは一度 JSON として解釈して
    から出力するので、ここで見ているのはフック自身の出力設定である。
    """
    finding = {"rule_id": "confusable_text", "title": "紛らわしい文字", "severity": "HIGH"}
    fake = make_fake_tirith(
        tmp_path, stdout=json.dumps({"action": "block", "findings": [finding]}), exit_code=1
    )
    proc = run_hook(bash_input("rm -rf /"), extra_env={"TIRITH_BIN": str(fake)})
    assert permission(proc) == "deny"
    assert "紛らわしい文字" in proc.stdout
    assert "\\u" not in proc.stdout


def test_warn_reports_context_without_a_decision(tmp_path: Path) -> None:
    """warn は判定を出さず警告文だけを載せる。

    ここで allow を明示すると permission プロンプトが飛び、tirith が「怪しい」と言った
    コマンドの方が、何も言わなかったコマンド (無出力 = 通常の権限フロー) より弱い審査で
    通ることになる。warn は稀ではない (finding の最大 severity が MEDIUM のときに返る)。
    """
    fake = make_fake_tirith(tmp_path, stdout=WARN_JSON, exit_code=2)
    proc = run_hook(bash_input("curl http://1.2.3.4"), extra_env={"TIRITH_BIN": str(fake)})
    assert proc.returncode == 0
    assert permission(proc) is None
    assert "suspicious URL" in context_text(proc)
    assert "MEDIUM" in context_text(proc)


def test_removed_warn_knob_no_longer_changes_the_outcome(tmp_path: Path) -> None:
    """判定の強さを選ぶノブは廃止した。設定が残っていても振る舞いは変わらない。

    ノブを読む経路が復活すると、warn の扱いが環境変数ひとつで allow へ戻せてしまう。
    閾値を動かしたいときは tirith 側の policy を使う。
    """
    fake = make_fake_tirith(tmp_path, stdout=WARN_JSON, exit_code=2)
    for value in ("deny", "allow", "bogus"):
        proc = run_hook(
            bash_input("curl http://1.2.3.4"),
            extra_env={"TIRITH_BIN": str(fake), "TIRITH_HOOK_WARN_ACTION": value},
        )
        assert permission(proc) is None, value
        assert "suspicious URL" in context_text(proc), value


def test_tirith_prefixed_variables_are_not_forwarded(tmp_path: Path) -> None:
    """tirith の子プロセスへ TIRITH_ 接頭辞を渡さない。

    tirith は検査の基礎を外から動かせる変数を持つ。フックが受け取った環境をそのまま渡すと
    それが検査を弱める経路になる。渡すのは TIRITH_INTEGRATION だけ。
    落ちたことは「エラー」ではなく「弱い判定」として返るので、実際に渡った集合を見る。
    """
    env_log = tmp_path / "forwarded-env.txt"
    fake = tmp_path / "fake-env-tirith.sh"
    # hook-event の fire-and-forget が同じファイルを上書きする race を避けるため check に絞る
    fake.write_text(
        '#!/bin/sh\n[ "$1" = check ] && env | grep "^TIRITH_" | sort > "$ENV_LOG"\nexit 0\n'
    )
    fake.chmod(0o755)

    run_hook(
        bash_input("echo hi"),
        extra_env={
            "TIRITH_BIN": str(fake),
            "TIRITH_POLICY_ROOT": str(tmp_path / "weakened"),
            "TIRITH_THREATDB_PATH": str(tmp_path / "empty-db"),
            "ENV_LOG": str(env_log),
        },
    )

    forwarded = env_log.read_text().split()
    assert forwarded == ["TIRITH_INTEGRATION=claude-code"]


# ---------------------------------------------------------------------------
# 異常系: fail-closed (既定 deny) / fail-open (TIRITH_FAIL_OPEN=1)
# ---------------------------------------------------------------------------


def test_unexpected_exit_code_fails_closed(tmp_path: Path) -> None:
    fake = make_fake_tirith(tmp_path, stdout="weird", exit_code=3)
    proc = run_hook(bash_input(), extra_env={"TIRITH_BIN": str(fake)})
    assert permission(proc) == "deny"


def test_nonzero_with_empty_stdout_fails_closed(tmp_path: Path) -> None:
    fake = make_fake_tirith(tmp_path, stdout="", exit_code=1)
    proc = run_hook(bash_input(), extra_env={"TIRITH_BIN": str(fake)})
    assert permission(proc) == "deny"


def test_empty_stdin_fails_closed() -> None:
    proc = run_hook(None)
    assert permission(proc) == "deny"
    assert "empty hook input" in reason_text(proc)


def test_invalid_json_stdin_fails_closed() -> None:
    proc = run_hook("{ this is not json")
    assert permission(proc) == "deny"
    assert "failed to parse hook input" in reason_text(proc)


def test_non_object_stdin_fails_closed() -> None:
    proc = run_hook("[]")
    assert permission(proc) == "deny"
    assert "invalid hook input format" in reason_text(proc)


def test_non_object_tool_input_fails_closed() -> None:
    bad = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": ["ls"]}
    proc = run_hook(bad)
    assert permission(proc) == "deny"
    assert "invalid tool_input format" in reason_text(proc)


def test_missing_command_fails_closed(tmp_path: Path) -> None:
    fake = make_fake_tirith(tmp_path, stdout=ALLOW_JSON, exit_code=0)
    bad = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {}}
    proc = run_hook(bad, extra_env={"TIRITH_BIN": str(fake)})
    assert permission(proc) == "deny"
    assert "no command found" in reason_text(proc)


def test_fail_open_env_allows_on_empty_stdin() -> None:
    proc = run_hook(None, extra_env={"TIRITH_FAIL_OPEN": "1"})
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


# ---------------------------------------------------------------------------
# passthrough: 対象外イベント/ツールは tirith を呼ばず素通り
# (block 偽バイナリを与えても deny されないことで「呼んでいない」を立証)
# ---------------------------------------------------------------------------


def test_non_bash_tool_passes_through(tmp_path: Path) -> None:
    fake = make_fake_tirith(tmp_path, stdout=BLOCK_JSON, exit_code=1)
    inp = {"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {"file_path": "/x"}}
    proc = run_hook(inp, extra_env={"TIRITH_BIN": str(fake)})
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_non_pretooluse_event_passes_through(tmp_path: Path) -> None:
    fake = make_fake_tirith(tmp_path, stdout=BLOCK_JSON, exit_code=1)
    inp = {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"}}
    proc = run_hook(inp, extra_env={"TIRITH_BIN": str(fake)})
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


# ---------------------------------------------------------------------------
# dual-case (camelCase / snake_case) フィールド抽出
# ---------------------------------------------------------------------------


def test_camelcase_fields_are_extracted(tmp_path: Path) -> None:
    fake = make_fake_tirith(tmp_path, stdout=BLOCK_JSON, exit_code=1)
    proc = run_hook(bash_input("rm -rf /", camel=True), extra_env={"TIRITH_BIN": str(fake)})
    assert permission(proc) == "deny"
    assert "dangerous rm" in reason_text(proc)


# ---------------------------------------------------------------------------
# バイナリ解決: TIRITH_BIN 設定ミス vs インフラ未整備
# ---------------------------------------------------------------------------


def test_tirith_bin_set_but_missing_fails_closed() -> None:
    # TIRITH_BIN を明示したのにパスが存在しない = 設定ミス → fail-closed (既定 deny)。
    proc = run_hook(bash_input(), extra_env={"TIRITH_BIN": "/nonexistent/tirith-xyz"})
    assert permission(proc) == "deny"


def test_tirith_bin_set_but_missing_respects_fail_open() -> None:
    proc = run_hook(
        bash_input(),
        extra_env={"TIRITH_BIN": "/nonexistent/tirith-xyz", "TIRITH_FAIL_OPEN": "1"},
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_binary_not_found_fails_open_but_says_so(tmp_path: Path) -> None:
    """バイナリ不在の fail-open は残すが、沈黙したことを文脈へ載せる。

    stderr 1 行だけだと、検査が消えたことがモデルの文脈に入らない。判定は出さないので
    通常の権限フローは壊れない。tirith 自身のテレメトリはここでは使えない (tirith が
    不在の状態なので、記録の呼び出しも同じ理由で失敗して握り潰される)。
    """
    proc = run_hook(
        bash_input(),
        extra_env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == 0
    assert permission(proc) is None
    assert "検査されていません" in context_text(proc)
    assert "見つからない" in proc.stderr
    # 復旧手順を pin する (guard_probes 側の同名の pin と対。理由はそちらのコメント)
    assert "brew install tirith" in context_text(proc)


# ---------------------------------------------------------------------------
# timeout: TIRITH_TIMEOUT 秒を超える tirith は fail-closed
# ---------------------------------------------------------------------------


def test_slow_tirith_times_out_and_fails_closed(tmp_path: Path) -> None:
    fake = make_fake_tirith(tmp_path, stdout=ALLOW_JSON, exit_code=0, sleep=2.0)
    proc = run_hook(
        bash_input(),
        extra_env={"TIRITH_BIN": str(fake), "TIRITH_TIMEOUT": "1"},
    )
    assert permission(proc) == "deny"
    assert "timed out" in reason_text(proc)


def test_invalid_timeout_falls_back_to_default(tmp_path: Path) -> None:
    # 不正値 'abc' は既定(10s)にフォールバックする。sleep 無し fake なら即 allow。
    # フォールバックが壊れ 0s 等が適用されると即 timeout→deny になり、このテストが落ちる。
    fake = make_fake_tirith(tmp_path, stdout=ALLOW_JSON, exit_code=0)
    proc = run_hook(bash_input(), extra_env={"TIRITH_BIN": str(fake), "TIRITH_TIMEOUT": "abc"})
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_nonpositive_timeout_falls_back_to_default(tmp_path: Path) -> None:
    # '0' が literal 適用されると subprocess timeout=0 で即 TimeoutExpired→deny になる。
    # 既定(10s)へフォールバックすれば sleep 無し fake は allow。
    fake = make_fake_tirith(tmp_path, stdout=ALLOW_JSON, exit_code=0)
    proc = run_hook(bash_input(), extra_env={"TIRITH_BIN": str(fake), "TIRITH_TIMEOUT": "0"})
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


# ---------------------------------------------------------------------------
# argv 構築: tirith に正しい引数（check/--json/posix/-- 区切り + command 末尾）が渡る
# ---------------------------------------------------------------------------


def test_tirith_invoked_with_correct_argv(tmp_path: Path) -> None:
    fake = make_fake_tirith(tmp_path, stdout=ALLOW_JSON, exit_code=0)
    arg_log = tmp_path / "argv.log"
    proc = run_hook(
        bash_input("echo hello world"),
        extra_env={"TIRITH_BIN": str(fake), "ARG_LOG": str(arg_log)},
    )
    assert proc.returncode == 0
    argv = arg_log.read_text().splitlines()
    # check サブコマンドと必須フラグ
    assert "check" in argv
    assert "--json" in argv
    assert "--non-interactive" in argv
    # --shell と posix を別々に検証する（--shell 欠落で posix が位置引数化する回帰を捕捉）
    assert "--shell" in argv
    assert "posix" in argv
    # command は argv 末尾、その直前は '--'（後続フラグ注入を防ぐ区切り）
    assert argv[-1] == "echo hello world"
    assert argv[-2] == "--"


# ---------------------------------------------------------------------------
# block + 非JSON stdout は raw テキストを reason にフォールバックする
# ---------------------------------------------------------------------------


def test_block_with_non_json_stdout_uses_raw_reason(tmp_path: Path) -> None:
    fake = make_fake_tirith(tmp_path, stdout="not json at all", exit_code=1)
    proc = run_hook(bash_input(), extra_env={"TIRITH_BIN": str(fake)})
    assert permission(proc) == "deny"
    assert "not json at all" in reason_text(proc)


def test_block_with_non_object_json_does_not_crash(tmp_path: Path) -> None:
    # 解釈可能だがオブジェクトでない JSON（配列）でも例外で decision を落とさず deny する。
    fake = make_fake_tirith(tmp_path, stdout="[1, 2, 3]", exit_code=1)
    proc = run_hook(bash_input(), extra_env={"TIRITH_BIN": str(fake)})
    assert permission(proc) == "deny"
