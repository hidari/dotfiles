"""apm-install-guard hook の黒箱テスト。

hook 本体をサブプロセス起動し、stdin に PreToolUse の JSON を流して stdout の
permissionDecision を検証する。モックは使わず、実 git リポジトリを tmp_path に作る。
test_tirith_hook.py と同じ流儀 (subprocess + 実物の代替物) で書いている。
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from conftest import HOOKS_DIR, REPO_ROOT

HOOK = HOOKS_DIR / "apm-install-guard.py"
BOOTSTRAP = REPO_ROOT / "bootstrap.sh"


def run_hook_raw(
    payload: str, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """stdin へ生の文字列を流してフックを起動する。

    基底環境から APM_INSTALL_GUARD_ 系を除いてから extra_env だけを適用する。実行環境に
    無効化フラグが立っていると、全テストが「無音 allow」で緑になってしまう。この除去を
    書き写した経路を作らないため、JSON を送る場合も生文字列を送る場合もここを通す。
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("APM_INSTALL_GUARD_")}
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def run_hook(
    body: dict[str, Any], extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return run_hook_raw(json.dumps(body), extra_env)


def decision(proc: subprocess.CompletedProcess[str]) -> str | None:
    """stdout の permissionDecision を返す。無音 (stdout 空) なら None。"""
    if not proc.stdout.strip():
        return None
    payload: dict[str, Any] = json.loads(proc.stdout)
    value = payload["hookSpecificOutput"]["permissionDecision"]
    assert isinstance(value, str)
    return value


def reason(proc: subprocess.CompletedProcess[str]) -> str:
    """deny の理由文を返す。

    stdout を素の文字列として検索してはいけない。json.dumps は既定で非 ASCII を \\uXXXX へ
    エスケープするため、パスに日本語が含まれると素の検索は必ず外れる。JSON として読めば
    ホスト側が見るのと同じ文字列が得られる。
    """
    payload: dict[str, Any] = json.loads(proc.stdout)
    value = payload["hookSpecificOutput"]["permissionDecisionReason"]
    assert isinstance(value, str)
    return value


def listed_paths(proc: subprocess.CompletedProcess[str]) -> list[str]:
    """deny 理由に並んだブロッカーのパスを返す。"""
    return [line[2:] for line in reason(proc).splitlines() if line.startswith("  ")]


def bash_blockers(repo: Path) -> list[str]:
    """層 1 (bootstrap.sh の apm_install_blockers) を実際に source して呼ぶ。

    text-parse せず bash 自身に解釈させる。BASH_SOURCE ガードがあるので source
    しても main は走らない。
    """
    script = f"source {shlex.quote(str(BOOTSTRAP))}; apm_install_blockers {shlex.quote(str(repo))}"
    proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True)
    return proc.stdout.splitlines()


def init_repo(path: Path) -> Path:
    """コミットを 1 つ持つ git リポジトリを作る。"""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, check=True)
    (path / "a.txt").write_text("hello\n")
    subprocess.run(["git", "add", "a.txt"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=path, check=True)
    return path


def body(command: str, cwd: str) -> dict[str, Any]:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": cwd,
    }


def test_clean_tree_allows_silently(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")

    proc = run_hook(body("apm install --frozen", str(repo)))

    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_dirty_tree_denies(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")

    proc = run_hook(body("apm install --frozen", str(repo)))

    # ブロックは exit code ではなく JSON で表す。exit は deny でも 0
    assert proc.returncode == 0
    assert decision(proc) == "deny"
    assert "a.txt" in reason(proc)


def test_untracked_file_denies(tmp_path: Path) -> None:
    """untracked は git から戻せないので、apm が消したときに復旧できない。"""
    repo = init_repo(tmp_path / "repo")
    (repo / "new.txt").write_text("x\n")

    proc = run_hook(body("apm install", str(repo)))

    assert decision(proc) == "deny"
    assert "new.txt" in reason(proc)


def test_apm_manifest_and_lockfile_are_allowed(tmp_path: Path) -> None:
    """apm install の入出力なので、これらだけが dirty なのは正常な中間状態。"""
    repo = init_repo(tmp_path / "repo")
    (repo / "home").mkdir()
    (repo / "home" / "apm.yml").write_text("name: x\n")
    (repo / "home" / "apm.lock.yaml").write_text("v: 1\n")
    subprocess.run(["git", "add", "home"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "add manifest"], cwd=repo, check=True)
    (repo / "home" / "apm.yml").write_text("name: y\n")
    (repo / "home" / "apm.lock.yaml").write_text("v: 2\n")

    proc = run_hook(body("cd home && apm install", str(repo)))

    assert proc.stdout.strip() == ""


def test_path_with_space_is_not_split(tmp_path: Path) -> None:
    """空白で分割すると 1 件が 2 件に化け、落ちた分は正常な結果として返るので気づけない。"""
    repo = init_repo(tmp_path / "repo")
    (repo / "has space.txt").write_text("x\n")

    proc = run_hook(body("apm install", str(repo)))

    assert decision(proc) == "deny"
    assert "has space.txt" in reason(proc)


def test_non_ascii_path_is_not_quoted(tmp_path: Path) -> None:
    """git は既定で非 ASCII をクォート表記にする。-z で生のまま受けていることを見る。"""
    repo = init_repo(tmp_path / "repo")
    (repo / "日本語ファイル.txt").write_text("x\n")

    proc = run_hook(body("apm install", str(repo)))

    assert decision(proc) == "deny"
    assert "日本語ファイル.txt" in reason(proc)


def test_renamed_path_is_reported_once_and_intact(tmp_path: Path) -> None:
    """porcelain -z の rename は "XY <to>\\0<from>\\0" の 2 チャンクで返る。

    from 側は状態フィールドを持たないため、全チャンクへ一律に 3 文字削りを適用すると
    存在しないパスが診断に並び、件数も水増しされる。診断は復旧の手掛かりなので、
    実在しないパスを並べるとガードそのものの信用が落ちる。
    """
    repo = init_repo(tmp_path / "repo")
    subprocess.run(["git", "mv", "a.txt", "renamed.txt"], cwd=repo, check=True)

    proc = run_hook(body("apm install", str(repo)))

    assert decision(proc) == "deny"
    assert listed_paths(proc) == ["renamed.txt"]
    assert "変更が 1 件" in reason(proc)


def test_rename_from_outside_the_allowed_manifest_is_a_blocker(tmp_path: Path) -> None:
    """移動先が許可対象でも、移動元が違えばそれは失われうる変更なので止める。"""
    repo = init_repo(tmp_path / "repo")
    (repo / "home").mkdir()
    subprocess.run(["git", "mv", "a.txt", "home/apm.yml"], cwd=repo, check=True)

    proc = run_hook(body("apm install", str(repo)))

    assert decision(proc) == "deny"
    # 壊れたパスではなく、その記録が指す実在のパスで報告すること
    assert listed_paths(proc) == ["home/apm.yml"]


def test_both_layers_agree_on_the_same_tree(tmp_path: Path) -> None:
    """層 1 (bash) と層 2 (python) が同じツリーで同じ判定を出すこと。

    プロセスが別で実装を共有できないため、片方だけ直しても双方のテストは緑のまま
    通ってしまう。実際 porcelain の rename パースは両方に同じ欠陥が入っていた。
    層をまたいだ一致は、どちらか一方のテストでは原理的に見えない。
    """

    def clean(_: Path) -> None:
        return None

    def modified(repo: Path) -> None:
        (repo / "a.txt").write_text("changed\n")

    def untracked(repo: Path) -> None:
        (repo / "new.txt").write_text("x\n")

    def only_manifest(repo: Path) -> None:
        (repo / "home").mkdir()
        (repo / "home" / "apm.yml").write_text("name: x\n")
        (repo / "home" / "apm.lock.yaml").write_text("v: 1\n")
        subprocess.run(["git", "add", "home"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "manifest"], cwd=repo, check=True)
        (repo / "home" / "apm.yml").write_text("name: y\n")

    def renamed(repo: Path) -> None:
        subprocess.run(["git", "mv", "a.txt", "renamed.txt"], cwd=repo, check=True)

    def path_with_space(repo: Path) -> None:
        (repo / "has space.txt").write_text("x\n")

    fixtures = {
        "clean": clean,
        "modified": modified,
        "untracked": untracked,
        "only_manifest": only_manifest,
        "renamed": renamed,
        "path_with_space": path_with_space,
    }

    for name, prepare in fixtures.items():
        repo = init_repo(tmp_path / name)
        prepare(repo)

        layer1 = bash_blockers(repo)
        layer2 = run_hook(body("apm install", str(repo)))

        assert bool(layer1) == (decision(layer2) == "deny"), f"{name}: layer1={layer1}"
        if layer1:
            assert sorted(layer1) == sorted(listed_paths(layer2)), name


def test_subcommands_outside_the_readonly_set_are_guarded(tmp_path: Path) -> None:
    """読み取り専用と確認できたもの以外は全て止める。

    install だけを見ると兄弟から bypass できる。さらに denylist だと apm が
    サブコマンドを増やすたびに黙って穴が開くため、判定は allowlist 側に置く。
    ここに並ぶ名前は apm --help (0.27.0) の実際の一覧から採っている。
    """
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")

    for command in (
        "apm install",
        "apm update",
        "apm prune",
        "apm uninstall dev-workflow",
        "apm deps clean",
        "apm deps update",
        # deploy 先ではなくても書き込むもの。allowlist 方式ではこれらも止まる
        "apm compile",
        "apm init",
        "apm pack",
        "apm unpack bundle.tgz",
        "apm mcp install foo",
        "apm run build",
    ):
        proc = run_hook(body(command, str(repo)))
        assert decision(proc) == "deny", command


def test_readonly_apm_subcommands_pass_through(tmp_path: Path) -> None:
    """読み取り専用のサブコマンドは何も書き換えないので止めない。

    このリストが allowlist の canonical な表現になる。ここから漏れたコマンドは
    dirty ツリーで止まるので、追加は「読み取り専用だと確認できた」ときだけ行う。
    """
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")

    for command in (
        "apm audit",
        "apm doctor",
        "apm find skill",
        "apm list",
        "apm outdated",
        "apm policy",
        "apm preview build",
        "apm search foo",
        "apm targets",
        "apm view dev-workflow",
        "apm deps list",
        "apm deps tree",
    ):
        proc = run_hook(body(command, str(repo)))
        assert proc.stdout.strip() == "", command


def test_flags_only_invocation_passes_through(tmp_path: Path) -> None:
    """サブコマンドを伴わない呼び出しは help を出すだけで何も書き換えない。"""
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")

    for command in ("apm", "apm --help", "apm --version", "apm -v"):
        proc = run_hook(body(command, str(repo)))
        assert proc.stdout.strip() == "", command


def test_operators_adjacent_to_words_are_still_detected(tmp_path: Path) -> None:
    """シェル演算子が語に密着してもトークン化が崩れないこと。

    shlex.split は ; & | ( ) を区切りとして扱わないため、素朴に使うと
    `apm install; git status` が `install;` という 1 トークンになり判定が外れる。
    ここが外れるとガードの主張 (dirty なら止まる) が静かに偽になる。
    """
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")

    for command in (
        "apm install; git status",
        "git stash&&apm install",
        "(apm install)",
        "apm install|tee log",
        "git status;apm prune",
    ):
        proc = run_hook(body(command, str(repo)))
        assert decision(proc) == "deny", command


def test_apm_as_an_argument_is_not_detected(tmp_path: Path) -> None:
    """コマンド位置にない apm は起動ではないので見ない。

    allowlist 方式では「読み取り専用一覧に無い語」が全て対象になるため、位置を
    問わずに拾うと `grep -rn apm bootstrap.sh` のような検索まで止まってしまう。
    """
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")

    for command in (
        "grep -rn apm bootstrap.sh",
        "which apm",
        "echo apm install",
        "git log --grep apm main",
    ):
        proc = run_hook(body(command, str(repo)))
        assert proc.stdout.strip() == "", command


def test_env_assignment_prefix_does_not_hide_the_invocation(tmp_path: Path) -> None:
    """VAR=x apm install の形はコマンド位置とみなす。"""
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")

    proc = run_hook(body("APM_LOG_LEVEL=DEBUG apm install", str(repo)))

    assert decision(proc) == "deny"


def test_quoted_string_is_not_detected(tmp_path: Path) -> None:
    """クォートされた文字列は 1 トークンになるのでコマンドとして誤検出されない。"""
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")

    proc = run_hook(body('echo "apm install"', str(repo)))

    assert proc.stdout.strip() == ""


def test_apm_after_an_operator_is_detected(tmp_path: Path) -> None:
    """連結の後ろでもコマンド位置なら検出する。"""
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")

    proc = run_hook(body("cd home && apm install --frozen", str(repo)))

    assert decision(proc) == "deny"


def test_cd_into_another_dirty_repository_is_detected(tmp_path: Path) -> None:
    """session cwd だけを見ると、コマンド内で別リポジトリへ移る経路が素通りする。

    ガードが生まれた原因 (apm がパッケージ外のファイルを消す) は、どのリポジトリで
    起きても同じ損失になる。session cwd が clean でも移動先が汚れていれば止める。
    """
    session = init_repo(tmp_path / "session")
    target = init_repo(tmp_path / "target")
    (target / "a.txt").write_text("changed\n")

    proc = run_hook(body(f"cd {target} && apm install --frozen", str(session)))

    assert decision(proc) == "deny"
    assert "a.txt" in reason(proc)


def test_cd_target_needing_expansion_falls_back_to_the_session_cwd(tmp_path: Path) -> None:
    """展開が要る cd 先は解決できない。検査を足せないだけで、緩くはしない。"""
    session = init_repo(tmp_path / "session")
    (session / "a.txt").write_text("changed\n")

    proc = run_hook(body('cd "$TARGET" && apm install', str(session)))

    assert decision(proc) == "deny"
    assert "a.txt" in reason(proc)


def test_relative_cd_inside_the_same_repository_stays_one_target(tmp_path: Path) -> None:
    """同一リポジトリ内の移動は root が同じなので判定は変わらない。"""
    repo = init_repo(tmp_path / "repo")
    (repo / "home").mkdir()

    proc = run_hook(body("cd home && apm install --frozen", str(repo)))

    assert proc.stdout.strip() == ""


def test_git_that_cannot_be_executed_denies(tmp_path: Path) -> None:
    """検査できなかったことを「リポジトリ外なので対象外」と同じ無音 allow に潰さない。"""
    repo = init_repo(tmp_path / "repo")
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()

    proc = run_hook(body("apm install", str(repo)), {"PATH": str(empty_bin)})

    assert decision(proc) == "deny"


def test_absolute_path_to_apm_is_detected(tmp_path: Path) -> None:
    """PATH を経由しない呼び出しでも basename で判定する。"""
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")

    proc = run_hook(body("/opt/homebrew/bin/apm install", str(repo)))

    assert decision(proc) == "deny"


def test_unrelated_command_passes_through(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")

    proc = run_hook(body("git status", str(repo)))

    assert proc.stdout.strip() == ""


def test_non_bash_tool_passes_through(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")
    payload = body("apm install", str(repo))
    payload["tool_name"] = "Read"

    proc = run_hook(payload)

    assert proc.stdout.strip() == ""


def test_non_pretooluse_event_passes_through(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")
    payload = body("apm install", str(repo))
    payload["hook_event_name"] = "PostToolUse"

    proc = run_hook(payload)

    assert proc.stdout.strip() == ""


def test_camel_case_fields_are_accepted(tmp_path: Path) -> None:
    """ホストがどちらの記法で送るかは版によるため両対応にしている。"""
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")

    proc = run_hook(
        {
            "hookEventName": "PreToolUse",
            "toolName": "Bash",
            "toolInput": {"command": "apm install"},
            "cwd": str(repo),
        }
    )

    assert decision(proc) == "deny"


def test_disable_env_var_turns_the_guard_off(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")

    proc = run_hook(body("apm install", str(repo)), {"APM_INSTALL_GUARD_DISABLE": "1"})

    assert proc.stdout.strip() == ""


def test_disable_env_var_only_accepts_one(tmp_path: Path) -> None:
    """うっかり APM_INSTALL_GUARD_DISABLE=0 と書いたときに無効化されないこと。"""
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")

    proc = run_hook(body("apm install", str(repo)), {"APM_INSTALL_GUARD_DISABLE": "0"})

    assert decision(proc) == "deny"


def test_non_git_cwd_passes_through(tmp_path: Path) -> None:
    """git が無ければ「git から戻す」前提そのものが無いので守備範囲外。"""
    plain = tmp_path / "plain"
    plain.mkdir()

    proc = run_hook(body("apm install", str(plain)))

    assert proc.stdout.strip() == ""


def test_unusable_input_denies() -> None:
    """入力が壊れている・空のときは素通りさせない (fail-closed)。"""
    for payload in ("{not json", ""):
        proc = run_hook_raw(payload)

        assert proc.returncode == 0, payload
        assert decision(proc) == "deny", payload


def test_missing_cwd_denies() -> None:
    """cwd が取れないとどのリポジトリを見ればよいか決まらないので許可しない。"""
    payload = body("apm install", "/nonexistent")
    del payload["cwd"]

    proc = run_hook(payload)

    assert decision(proc) == "deny"


def test_missing_command_denies(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    payload = body("apm install", str(repo))
    payload["tool_input"] = {}

    proc = run_hook(payload)

    assert decision(proc) == "deny"
