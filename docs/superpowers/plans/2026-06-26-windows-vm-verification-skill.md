# windows-vm-verification Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** VMware Fusion 上の Windows 検証 VM を「繋ぐ・直す・調べる・検証する」操作を、プロジェクト非依存の generic skill `windows-vm-verification` (CLI `winvm`) に切り出し、relay の xtask を PATH 上の `winvm` を呼ぶ薄いラッパーへ縮小する。

**Architecture:** dotfiles に generic な uv 単一ファイル CLI `winvm.py` (subcommand: resolve-ip / recover / health / run) を置き、純粋ロジックを `test_winvm.py` で固定する。bootstrap が `winvm.py` を `~/.local/bin/winvm` へ symlink し PATH コマンド化。relay は `Command::new("winvm")` を relay 設定で呼ぶだけにする。VM 固有値 (.vmx パス・ssh host・repo パス・コマンド) は全て呼び出し側が注入し、CLI 本体はハードコードしない。

**Tech Stack:** Python 3 (stdlib のみ) + uv (PEP723 single-file script), pytest, Rust (relay xtask の薄いラッパー), ssh/scp/vmrun (外部 CLI)。

設計 spec: `docs/superpowers/specs/2026-06-26-windows-vm-verification-skill-design.md`

## Global Constraints

- CLI 本体に VM 固有値をハードコードしない。設定は引数 + env (`WINVM_VMX` / `WINVM_HOST` / `WINVM_REPO` / `WINVM_BASE` / `WINVM_LEASES`)、引数が env を上書き
- 公開リポ (dotfiles) に置くため秘密・個人パスを含めない (テストは temp ファイル/合成データで行う)
- MAC は `.vmx` の `ethernet0.generatedAddress` (static 時 `ethernet0.address`) から導出。ハードコード禁止
- 純粋ロジックは exact assertion + negative case で固定。`uv run --with pytest python -m pytest` で skill 単体で緑 (pyproject.toml は作らない = 単一ファイル設計を維持)
- PowerShell は scp + `powershell -File` で渡す (cmd 8191 字制限回避)。スクリプトは ASCII ラベル + `[Console]::OutputEncoding=UTF8`
- `recover` は `vmware-vmx` プロセス稼働中は中止 (多層防御)、既定は backup へ移動 (可逆)
- lease ファイル既定 `/var/db/vmware/vmnet-dhcpd-vmnet8.leases`
- skill ディレクトリ: `home/.claude/skills/windows-vm-verification/`

---

## Phase 1: generic skill (dotfiles)

### Task 1: scaffold + `extract_mac_from_vmx`

**Files:**
- Create: `home/.claude/skills/windows-vm-verification/winvm.py`
- Create: `home/.claude/skills/windows-vm-verification/test_winvm.py`

**Interfaces:**
- Produces: `extract_mac_from_vmx(vmx_text: str) -> str | None` — `.vmx` 本文から NIC MAC を小文字で返す。`generatedAddress` 優先、無ければ `address`、どちらも無ければ `None`

- [ ] **Step 1: 失敗するテストを書く**

`home/.claude/skills/windows-vm-verification/test_winvm.py`:

```python
import winvm


def test_extract_mac_prefers_generated_address():
    vmx = (
        'ethernet0.connectionType = "nat"\n'
        'ethernet0.addressType = "generated"\n'
        'ethernet0.generatedAddress = "00:0C:29:B0:EA:5A"\n'
    )
    assert winvm.extract_mac_from_vmx(vmx) == "00:0c:29:b0:ea:5a"


def test_extract_mac_falls_back_to_static_address():
    vmx = 'ethernet0.addressType = "static"\nethernet0.address = "00:50:56:AB:CD:EF"\n'
    assert winvm.extract_mac_from_vmx(vmx) == "00:50:56:ab:cd:ef"


def test_extract_mac_returns_none_when_absent():
    assert winvm.extract_mac_from_vmx('displayName = "x"\n') is None
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd home/.claude/skills/windows-vm-verification && uv run --with pytest python -m pytest test_winvm.py -v`
Expected: FAIL (`AttributeError: module 'winvm' has no attribute 'extract_mac_from_vmx'` または import 失敗)

- [ ] **Step 3: 最小実装**

`home/.claude/skills/windows-vm-verification/winvm.py` (先頭から):

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""windows-vm-verification: VMware Fusion 上の Windows VM を繋ぐ/直す/調べる/検証する generic CLI。"""
from __future__ import annotations

import re


def extract_mac_from_vmx(vmx_text: str) -> str | None:
    """`.vmx` 本文から NIC MAC を小文字で返す (generatedAddress 優先、無ければ address)。"""
    for key in ("ethernet0.generatedAddress", "ethernet0.address"):
        m = re.search(rf'^\s*{re.escape(key)}\s*=\s*"([^"]+)"', vmx_text, re.MULTILINE)
        if m:
            return m.group(1).strip().lower()
    return None
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd home/.claude/skills/windows-vm-verification && uv run --with pytest python -m pytest test_winvm.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: コミット**

```bash
git add home/.claude/skills/windows-vm-verification/winvm.py home/.claude/skills/windows-vm-verification/test_winvm.py
git commit -m "feat: winvm-verification skill scaffold + extract_mac_from_vmx"
```

---

### Task 2: `parse_latest_lease_ip` + `resolve-ip` subcommand

**Files:**
- Modify: `home/.claude/skills/windows-vm-verification/winvm.py`
- Modify: `home/.claude/skills/windows-vm-verification/test_winvm.py`

**Interfaces:**
- Consumes: `extract_mac_from_vmx`
- Produces:
  - `parse_latest_lease_ip(leases_text: str, mac: str) -> str | None` — 同一 MAC の最新 lease ブロックの IP。無一致は `None`
  - `cmd_resolve_ip(args) -> int` — `--vmx` から MAC 導出 → `--leases` を読んで IP を stdout。無一致は非ゼロ

- [ ] **Step 1: 失敗するテストを書く**

`test_winvm.py` に追記:

```python
LEASES = """
lease 172.16.237.130 {
\thardware ethernet 00:0c:29:bb:8b:20;
}
lease 172.16.237.129 {
\thardware ethernet 00:0c:29:b0:ea:5a;
}
lease 172.16.237.129 {
\thardware ethernet 00:0c:29:b0:ea:5a;
}
"""


def test_parse_latest_lease_ip_returns_latest_matching_block():
    assert winvm.parse_latest_lease_ip(LEASES, "00:0c:29:b0:ea:5a") == "172.16.237.129"


def test_parse_latest_lease_ip_is_case_insensitive_on_mac():
    assert winvm.parse_latest_lease_ip(LEASES, "00:0C:29:BB:8B:20") == "172.16.237.130"


def test_parse_latest_lease_ip_returns_none_when_no_match():
    assert winvm.parse_latest_lease_ip(LEASES, "de:ad:be:ef:00:00") is None
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run --with pytest python -m pytest test_winvm.py -k lease -v`
Expected: FAIL (`parse_latest_lease_ip` 未定義)

- [ ] **Step 3: 最小実装**

`winvm.py` に追記:

```python
def parse_latest_lease_ip(leases_text: str, mac: str) -> str | None:
    """同一 MAC の最後の lease ブロックの IP を返す (lease は時系列追記、最後が現在値)。"""
    mac = mac.lower()
    current_ip: str | None = None
    latest: str | None = None
    for line in leases_text.splitlines():
        s = line.strip()
        if s.startswith("lease "):
            current_ip = s.split()[1]
        elif s.startswith("hardware ethernet"):
            m = s.split()[2].rstrip(";").lower()
            if m == mac:
                latest = current_ip
    return latest
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run --with pytest python -m pytest test_winvm.py -k lease -v`
Expected: PASS (3 passed)

- [ ] **Step 5: `resolve-ip` subcommand + argparse 骨格を実装**

`winvm.py` の末尾に追記:

```python
import argparse
import sys
from pathlib import Path

DEFAULT_LEASES = "/var/db/vmware/vmnet-dhcpd-vmnet8.leases"


def _env_or(arg_value: str | None, env_key: str, default: str | None = None) -> str | None:
    import os
    return arg_value or os.environ.get(env_key) or default


def cmd_resolve_ip(args: argparse.Namespace) -> int:
    vmx = _env_or(args.vmx, "WINVM_VMX")
    leases = _env_or(args.leases, "WINVM_LEASES", DEFAULT_LEASES)
    if not vmx:
        print("error: --vmx (または WINVM_VMX) が必要です", file=sys.stderr)
        return 2
    mac = extract_mac_from_vmx(Path(vmx).read_text(encoding="utf-8", errors="replace"))
    if not mac:
        print(f"error: .vmx から MAC を導出できません: {vmx}", file=sys.stderr)
        return 1
    ip = parse_latest_lease_ip(Path(leases).read_text(encoding="utf-8", errors="replace"), mac)
    if not ip:
        print(f"error: MAC {mac} に一致する lease がありません (VM 未起動?)", file=sys.stderr)
        return 1
    print(ip)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="winvm", description="VMware Fusion Windows VM ops/verify")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("resolve-ip", help="VMware NAT lease から VM の現 IP を解決")
    sp.add_argument("--vmx")
    sp.add_argument("--leases")
    sp.set_defaults(func=cmd_resolve_ip)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: resolve-ip の統合テストを書いて通す**

`test_winvm.py` に追記:

```python
def test_cmd_resolve_ip_end_to_end(tmp_path, capsys):
    vmx = tmp_path / "vm.vmx"
    vmx.write_text('ethernet0.generatedAddress = "00:0c:29:b0:ea:5a"\n', encoding="utf-8")
    leases = tmp_path / "leases"
    leases.write_text(LEASES, encoding="utf-8")
    rc = winvm.main(["resolve-ip", "--vmx", str(vmx), "--leases", str(leases)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "172.16.237.129"


def test_cmd_resolve_ip_no_lease_is_nonzero(tmp_path):
    vmx = tmp_path / "vm.vmx"
    vmx.write_text('ethernet0.generatedAddress = "de:ad:be:ef:00:00"\n', encoding="utf-8")
    leases = tmp_path / "leases"
    leases.write_text(LEASES, encoding="utf-8")
    assert winvm.main(["resolve-ip", "--vmx", str(vmx), "--leases", str(leases)]) == 1
```

Run: `uv run --with pytest python -m pytest test_winvm.py -v`
Expected: PASS (all)

- [ ] **Step 7: コミット**

```bash
git add home/.claude/skills/windows-vm-verification/winvm.py home/.claude/skills/windows-vm-verification/test_winvm.py
git commit -m "feat: winvm resolve-ip (.vmx MAC 由来で lease から IP 解決)"
```

---

### Task 3: `run` 純粋ロジック (sync 計算)

winvm_check.rs の純粋ロジックを Python へ移植する。

**Files:**
- Modify: `home/.claude/skills/windows-vm-verification/winvm.py`
- Modify: `home/.claude/skills/windows-vm-verification/test_winvm.py`

**Interfaces:**
- Produces:
  - `files_to_sync(branch_delta: str, working_delta: str, untracked: str) -> list[str]` — 行をトリム/空行除去/重複排除/安定ソート
  - `to_windows_path(path: str) -> str` — `/` を `\` に
  - `resolve_diff_base(vm_head: str, vm_head_known: bool, fallback: str) -> str`
  - `mkdir_command(repo_win: str, files: list[str]) -> str | None` — 親ディレクトリを dedup し `if not exist ... mkdir ...` を ` & ` 連結。直下のみなら `None`

- [ ] **Step 1: 失敗するテストを書く**

`test_winvm.py` に追記:

```python
def test_files_to_sync_dedups_blank_strips_sorts():
    got = winvm.files_to_sync("b/x.rs\na.rs\n", "a.rs\n\n  c.rs  \n", "d.rs\n")
    assert got == ["a.rs", "b/x.rs", "c.rs", "d.rs"]


def test_files_to_sync_empty_inputs_return_empty():
    assert winvm.files_to_sync("", "  \n", "\n") == []


def test_to_windows_path():
    assert winvm.to_windows_path("C:/proj/app") == "C:\\proj\\app"
    assert winvm.to_windows_path("a") == "a"


def test_resolve_diff_base():
    assert winvm.resolve_diff_base("abc123", True, "main") == "abc123"
    assert winvm.resolve_diff_base("deadbeef", False, "main") == "main"


def test_mkdir_command_dedups_parents():
    files = ["crates/xtask/src/a.rs", "crates/xtask/src/b.rs", "crates/core/c.rs"]
    cmd = winvm.mkdir_command("C:\\repo", files)
    assert cmd == (
        'if not exist "C:\\repo\\crates\\core" mkdir "C:\\repo\\crates\\core" & '
        'if not exist "C:\\repo\\crates\\xtask\\src" mkdir "C:\\repo\\crates\\xtask\\src"'
    )


def test_mkdir_command_root_only_returns_none():
    assert winvm.mkdir_command("C:\\repo", ["Cargo.toml", "README.md"]) is None
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run --with pytest python -m pytest test_winvm.py -k "files_to_sync or windows_path or diff_base or mkdir" -v`
Expected: FAIL (未定義)

- [ ] **Step 3: 最小実装**

`winvm.py` に追記:

```python
def files_to_sync(branch_delta: str, working_delta: str, untracked: str) -> list[str]:
    s: set[str] = set()
    for block in (branch_delta, working_delta, untracked):
        for line in block.splitlines():
            t = line.strip()
            if t:
                s.add(t)
    return sorted(s)


def to_windows_path(path: str) -> str:
    return path.replace("/", "\\")


def resolve_diff_base(vm_head: str, vm_head_known: bool, fallback: str) -> str:
    return vm_head if vm_head_known else fallback


def mkdir_command(repo_win: str, files: list[str]) -> str | None:
    parents = set()
    for f in files:
        parent = str(Path(f).parent)
        if parent and parent != ".":
            parents.add(f"{repo_win}\\{to_windows_path(parent)}")
    if not parents:
        return None
    return " & ".join(f'if not exist "{p}" mkdir "{p}"' for p in sorted(parents))
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run --with pytest python -m pytest test_winvm.py -v`
Expected: PASS (all)

- [ ] **Step 5: コミット**

```bash
git add home/.claude/skills/windows-vm-verification/winvm.py home/.claude/skills/windows-vm-verification/test_winvm.py
git commit -m "feat: winvm run の純粋ロジック (sync 計算) を移植"
```

---

### Task 4: `run` subcommand orchestration (ssh/scp)

**Files:**
- Modify: `home/.claude/skills/windows-vm-verification/winvm.py`
- Modify: `home/.claude/skills/windows-vm-verification/test_winvm.py`

**Interfaces:**
- Consumes: `files_to_sync`, `to_windows_path`, `resolve_diff_base`, `mkdir_command`
- Produces:
  - `git_local(args: list[str]) -> str` — ローカル git stdout (subprocess)
  - `ssh_capture(host, remote) -> str`, `run_ssh(host, remote) -> bool`, `scp(host, local, dest) -> bool` (subprocess)
  - `cmd_run(args) -> int` — VM HEAD を base に sync → reset → scp → remote 実行

- [ ] **Step 1: テスト (pure な remote コマンド組立) を書く**

reset/remote コマンド文字列の組立だけ純粋関数に切り出して固定する。`test_winvm.py` に追記:

```python
def test_remote_reset_command():
    assert winvm.remote_reset_command("C:\\repo") == (
        'cd /d "C:\\repo" && git checkout -- . && git clean -fd'
    )


def test_remote_exec_command():
    assert winvm.remote_exec_command("C:\\repo", "cargo xtask check-desktop") == (
        'cd /d "C:\\repo" && cargo xtask check-desktop'
    )
```

- [ ] **Step 2: 失敗を確認**

Run: `uv run --with pytest python -m pytest test_winvm.py -k "reset_command or exec_command" -v`
Expected: FAIL (未定義)

- [ ] **Step 3: 実装 (pure helpers + orchestration)**

`winvm.py` に追記:

```python
import subprocess


def remote_reset_command(repo_win: str) -> str:
    return f'cd /d "{repo_win}" && git checkout -- . && git clean -fd'


def remote_exec_command(repo_win: str, remote_cmd: str) -> str:
    return f'cd /d "{repo_win}" && {remote_cmd}'


def git_local(args: list[str]) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout


def ssh_capture(host: str, remote: str) -> str:
    return subprocess.run(["ssh", host, remote], capture_output=True, text=True).stdout


def run_ssh(host: str, remote: str) -> bool:
    return subprocess.run(["ssh", host, remote]).returncode == 0


def scp(host: str, local: str, dest: str) -> bool:
    return subprocess.run(["scp", "-q", local, f"{host}:{dest}"]).returncode == 0


def cmd_run(args: argparse.Namespace) -> int:
    host = _env_or(args.host, "WINVM_HOST")
    repo = _env_or(args.repo, "WINVM_REPO")
    base = _env_or(args.base, "WINVM_BASE", "main")
    if not host or not repo:
        print("error: --host と --repo (または env) が必要です", file=sys.stderr)
        return 2
    repo_win = to_windows_path(repo)

    vm_head = ssh_capture(host, f'cd /d "{repo_win}" && git rev-parse HEAD').strip()
    vm_head_known = bool(vm_head) and (
        subprocess.run(["git", "cat-file", "-e", f"{vm_head}^{{commit}}"]).returncode == 0
    )
    diff_base = resolve_diff_base(vm_head, vm_head_known, base)
    if not vm_head_known:
        print(f"警告: VM HEAD ({vm_head[:7]}) をローカル解決できず base={base} にフォールバック", file=sys.stderr)

    files = [
        f
        for f in files_to_sync(
            git_local(["diff", "--name-only", diff_base, "HEAD"]),
            git_local(["diff", "--name-only", "HEAD"]),
            git_local(["ls-files", "--others", "--exclude-standard"]),
        )
        if Path(f).is_file()
    ]
    if not files:
        if args.skip_when_no_changes:
            print(f"同期する変更ファイルがありません ({diff_base}..HEAD + working tree)")
            return 0
        print(f"同期対象なし。VM の現状で実行します ({diff_base}..HEAD)")

    if not run_ssh(host, remote_reset_command(repo_win)):
        print("VM の reset に失敗しました", file=sys.stderr)
        return 1
    if files:
        mk = mkdir_command(repo_win, files)
        if mk and not run_ssh(host, mk):
            print("VM のディレクトリ作成に失敗しました", file=sys.stderr)
            return 1
        for f in files:
            if not scp(host, f, f"{repo}/{f}"):
                print(f"scp 失敗: {f}", file=sys.stderr)
                return 1

    remote_cmd = " ".join(args.remote)
    print(f"=== VM で {remote_cmd} を実行 ===")
    return 0 if run_ssh(host, remote_exec_command(repo_win, remote_cmd)) else 1
```

`build_parser()` に subcommand を追加 (resolve-ip の set_defaults の後):

```python
    rp = sub.add_parser("run", help="git 差分を scp 同期して remote コマンド実行")
    rp.add_argument("--host")
    rp.add_argument("--repo")
    rp.add_argument("--base")
    rp.add_argument("--skip-when-no-changes", action="store_true")
    rp.add_argument("remote", nargs=argparse.REMAINDER, help="-- の後に remote コマンド")
    rp.set_defaults(func=cmd_run)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run --with pytest python -m pytest test_winvm.py -v`
Expected: PASS (all)

- [ ] **Step 5: コミット**

```bash
git add home/.claude/skills/windows-vm-verification/winvm.py home/.claude/skills/windows-vm-verification/test_winvm.py
git commit -m "feat: winvm run subcommand (sync-and-run)"
```

---

### Task 5: `health` subcommand

**Files:**
- Modify: `home/.claude/skills/windows-vm-verification/winvm.py`
- Modify: `home/.claude/skills/windows-vm-verification/test_winvm.py`

**Interfaces:**
- Produces:
  - `build_health_powershell(check_tools: list[str], repo: str | None) -> str` — ASCII ラベル + `[Console]::OutputEncoding=UTF8` を含み、指定 tool の `--version` チェック行を含む PowerShell 本文
  - `cmd_health(args) -> int` — `.ps1` を scp して `powershell -File` 実行、後始末

- [ ] **Step 1: 失敗するテストを書く**

`test_winvm.py` に追記:

```python
def test_build_health_powershell_includes_encoding_and_tools():
    ps = winvm.build_health_powershell(["node", "cargo"], "C:/proj/app")
    assert "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8" in ps
    assert "fsutil dirty query C:" in ps
    assert "'node'" in ps and "'cargo'" in ps
    assert "C:/proj/app" in ps


def test_build_health_powershell_no_repo_omits_repo_section():
    ps = winvm.build_health_powershell(["node"], None)
    assert "repo state" not in ps
```

- [ ] **Step 2: 失敗を確認**

Run: `uv run --with pytest python -m pytest test_winvm.py -k health -v`
Expected: FAIL (未定義)

- [ ] **Step 3: 実装**

`winvm.py` に追記 (本文は spec の health スクリプトを ASCII 化したもの。tools と repo を埋め込む):

```python
def build_health_powershell(check_tools: list[str], repo: str | None) -> str:
    tools = ", ".join(f"'{t}'" for t in check_tools)
    lines = [
        "$ErrorActionPreference = 'Continue'",
        "try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}",
        "Write-Output '===== OS / Boot ====='",
        "$os = Get-CimInstance Win32_OperatingSystem",
        "Write-Output ('LastBootUp : ' + $os.LastBootUpTime)",
        "Write-Output '===== Volumes (Healthy is OK) ====='",
        "Get-Volume | Where-Object { $_.DriveLetter } | Format-Table DriveLetter, FileSystemType, HealthStatus -AutoSize | Out-String -Width 200",
        "Write-Output '===== NTFS dirty bit (NOT Dirty is OK) ====='",
        "(& cmd /c 'fsutil dirty query C:') 2>&1 | Out-String",
        "Write-Output '===== Unexpected shutdown (41/6008/1001) ====='",
        "Get-WinEvent -FilterHashtable @{LogName='System'; Id=41,6008,1001} -MaxEvents 6 -ErrorAction SilentlyContinue | Select-Object TimeCreated, Id | Format-Table -AutoSize | Out-String",
        "Write-Output '===== NTFS corruption events (0 is OK) ====='",
        "$ntfs = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Ntfs'} -MaxEvents 15 -ErrorAction SilentlyContinue | Where-Object { $_.LevelDisplayName -in 'Error','Warning' }",
        "if ($ntfs) { $ntfs | Format-Table TimeCreated, Id, LevelDisplayName -AutoSize | Out-String } else { Write-Output '  (none = OK)' }",
        "Write-Output '===== dev toolchain ====='",
        f"foreach ($t in @({tools})) {{ $c = Get-Command $t -ErrorAction SilentlyContinue; if ($c) {{ Write-Output ('  ' + $t + ': ' + ((& $t --version 2>&1 | Select-Object -First 1))) }} else {{ Write-Output ('  ' + $t + ': (not found)') }} }}",
    ]
    if repo:
        lines += [
            "Write-Output '===== repo state ====='",
            f"if (Test-Path '{repo}') {{ Push-Location '{repo}'; Write-Output ('  HEAD: ' + (git rev-parse --short HEAD 2>&1) + ' ' + (git rev-parse --abbrev-ref HEAD 2>&1)); Pop-Location }}",
        ]
    lines.append("Write-Output '===== HEALTHCHECK DONE ====='")
    return "\n".join(lines) + "\n"


def cmd_health(args: argparse.Namespace) -> int:
    host = _env_or(args.host, "WINVM_HOST")
    repo = _env_or(args.repo, "WINVM_REPO")
    if not host:
        print("error: --host (または WINVM_HOST) が必要です", file=sys.stderr)
        return 2
    tools = args.check_tools.split(",") if args.check_tools else []
    ps = build_health_powershell([t for t in tools if t], repo)
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as fh:
        fh.write(ps)
        local = fh.name
    remote = "C:/Users/Public/winvm_health.ps1"
    try:
        if not scp(host, local, remote):
            print("health スクリプトの scp に失敗しました", file=sys.stderr)
            return 1
        ok = run_ssh(host, f"powershell -NoProfile -ExecutionPolicy Bypass -File {remote}")
        run_ssh(host, f"powershell -NoProfile -Command Remove-Item -Force {remote}")
        return 0 if ok else 1
    finally:
        Path(local).unlink(missing_ok=True)
```

`build_parser()` に追加:

```python
    hp = sub.add_parser("health", help="SSH 越しに VM の健全性を検査")
    hp.add_argument("--host")
    hp.add_argument("--repo")
    hp.add_argument("--check-tools", help="カンマ区切り (例: node,pnpm,cargo,rustc,git)")
    hp.set_defaults(func=cmd_health)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run --with pytest python -m pytest test_winvm.py -v`
Expected: PASS (all)

- [ ] **Step 5: コミット**

```bash
git add -A home/.claude/skills/windows-vm-verification/
git commit -m "feat: winvm health subcommand (NTFS/dirty bit/toolchain 検査)"
```

---

### Task 6: `recover` subcommand (stale lock 除去)

**Files:**
- Modify: `home/.claude/skills/windows-vm-verification/winvm.py`
- Modify: `home/.claude/skills/windows-vm-verification/test_winvm.py`

**Interfaces:**
- Produces:
  - `find_stale_lock_dirs(bundle_dir: Path) -> list[Path]` — バンドル直下の `*.lck` ディレクトリ一覧
  - `cmd_recover(args) -> int` — vmware-vmx 稼働中は中止、`*.lck` を backup へ移動 (既定) / `--dry-run`

- [ ] **Step 1: 失敗するテストを書く**

`test_winvm.py` に追記:

```python
def test_find_stale_lock_dirs(tmp_path):
    (tmp_path / "disk.vmdk.lck").mkdir()
    (tmp_path / "disk.vmdk.lck" / "M1.lck").write_text("x")
    (tmp_path / "disk.vmdk").write_text("descriptor")
    found = winvm.find_stale_lock_dirs(tmp_path)
    assert [p.name for p in found] == ["disk.vmdk.lck"]


def test_find_stale_lock_dirs_none(tmp_path):
    (tmp_path / "disk.vmdk").write_text("x")
    assert winvm.find_stale_lock_dirs(tmp_path) == []
```

- [ ] **Step 2: 失敗を確認**

Run: `uv run --with pytest python -m pytest test_winvm.py -k stale_lock -v`
Expected: FAIL (未定義)

- [ ] **Step 3: 実装**

`winvm.py` に追記:

```python
import shutil


def find_stale_lock_dirs(bundle_dir: Path) -> list[Path]:
    return sorted(p for p in bundle_dir.glob("*.lck") if p.is_dir())


def _vmware_vmx_running() -> bool:
    out = subprocess.run(["pgrep", "-f", "vmware-vmx"], capture_output=True, text=True)
    return out.returncode == 0


def cmd_recover(args: argparse.Namespace) -> int:
    vmx = _env_or(args.vmx, "WINVM_VMX")
    if not vmx:
        print("error: --vmx (または WINVM_VMX) が必要です", file=sys.stderr)
        return 2
    bundle = Path(vmx).parent
    if _vmware_vmx_running():
        print("中止: vmware-vmx プロセスが稼働中です。VM を停止してから実行してください", file=sys.stderr)
        return 1
    locks = find_stale_lock_dirs(bundle)
    if not locks:
        print("stale ロックはありません")
        return 0
    for lk in locks:
        if args.dry_run:
            print(f"[dry-run] 除去対象: {lk}")
            continue
        if args.backup:
            dest = Path(args.backup) / lk.name
            Path(args.backup).mkdir(parents=True, exist_ok=True)
            shutil.move(str(lk), str(dest))
            print(f"退避: {lk} -> {dest}")
        else:
            shutil.rmtree(lk)
            print(f"削除: {lk}")
    return 0
```

`build_parser()` に追加:

```python
    cp = sub.add_parser("recover", help="stale *.lck を除去し起動不能を解消")
    cp.add_argument("--vmx")
    cp.add_argument("--backup", help="削除でなく退避先へ移動 (可逆)")
    cp.add_argument("--dry-run", action="store_true")
    cp.set_defaults(func=cmd_recover)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run --with pytest python -m pytest test_winvm.py -v`
Expected: PASS (all)

- [ ] **Step 5: コミット**

```bash
git add -A home/.claude/skills/windows-vm-verification/
git commit -m "feat: winvm recover subcommand (stale lock 除去)"
```

---

### Task 7: SKILL.md + references

**Files:**
- Create: `home/.claude/skills/windows-vm-verification/SKILL.md`
- Create: `home/.claude/skills/windows-vm-verification/references/ssh-config.template`
- Create: `home/.claude/skills/windows-vm-verification/references/troubleshooting.md`

- [ ] **Step 1: SKILL.md を書く**

frontmatter + 本文。description は「いつ使うか」を具体的に (起動不能復旧 / SSH 健全性確認 / cfg(windows) 検証 / IP 解決)。本文に4サブコマンドの使い方、env 規約、接続セットアップ (ssh config + key)、`winvm recover` の手順、PowerShell の cmd 8191 字制限と UTF-8 の注意を記す。MAC は `.vmx` 由来でドリフトしない点を明記。

```markdown
---
name: windows-vm-verification
description: VMware Fusion 上の Windows 検証 VM を繋ぐ/直す/調べる/検証する generic CLI (winvm)。起動不能 ("ディレクトリが空ではありません" = stale disk lock) の復旧、SSH 越しの NTFS/health 確認、cfg(windows) コードの remote 検証 (ローカル変更を scp 同期して remote コマンド実行)、NAT DHCP からの IP 解決を扱う。VMware Fusion の Windows VM を操作・検証する時に使う。
---
```

(本文は spec の各節を generic 視点で記述。relay 固有値は例として示すに留める)

- [ ] **Step 2: references を書く**

`ssh-config.template`: `Host <alias>` に `ProxyCommand sh -c 'exec nc "$(winvm resolve-ip --vmx <path>)" 22'`、`HostKeyAlias`、`IdentityFile`、`StrictHostKeyChecking accept-new` を含む雛形。

`troubleshooting.md`: 「起動時 "ディレクトリが空ではありません"」→ `winvm recover`、「nc が Host is down」→ stale lease (VM 未起動 or 別 IP)、「SSH banner timeout」→ sshd 起動待ち、を表で。

- [ ] **Step 3: コミット**

```bash
git add -A home/.claude/skills/windows-vm-verification/
git commit -m "docs: winvm-verification SKILL.md + references"
```

---

### Task 8: PATH コマンド化 (bootstrap) + 手動検証

**Files:**
- Modify: `bootstrap.sh` (SYMLINK_PAIRS に 1 行追加)

- [ ] **Step 1: winvm.py に実行権限を付与**

```bash
chmod +x home/.claude/skills/windows-vm-verification/winvm.py
```

- [ ] **Step 2: SYMLINK_PAIRS に追加**

`bootstrap.sh` の `SYMLINK_PAIRS=(` 配列に追記 (`home/.claude/skills|.claude/skills` の行の近く):

```bash
    "home/.claude/skills/windows-vm-verification/winvm.py|.local/bin/winvm"
```

- [ ] **Step 3: symlink を作成して検証**

```bash
ln -sf "$PWD/home/.claude/skills/windows-vm-verification/winvm.py" "$HOME/.local/bin/winvm"
winvm resolve-ip --help
```
Expected: resolve-ip の usage が表示される (PATH から `winvm` が引け、uv が起動する)

- [ ] **Step 4: コミット**

```bash
git add bootstrap.sh home/.claude/skills/windows-vm-verification/winvm.py
git commit -m "build: winvm を ~/.local/bin へ symlink し PATH コマンド化"
```

---

## Phase 2: relay 移行 (relay リポジトリ)

> 作業ディレクトリは relay リポジトリ (`~/Develop/relay`)。Phase 1 完了 (= `winvm` が PATH にある) が前提。

### Task 9: relay xtask を薄いラッパーへ

**Files:**
- Modify: `crates/xtask/src/winvm_check.rs` (大幅縮小)

**Interfaces:**
- Consumes: PATH 上の `winvm` CLI

- [ ] **Step 1: 失敗するテストを書く (argv 構築の純粋ロジック)**

`crates/xtask/src/winvm_check.rs` の `#[cfg(test)] mod spec` を以下に置換 (純粋ロジックは Python へ移ったので、relay 側は argv 構築のみ残す):

```rust
#[cfg(test)]
mod spec {
    use super::*;

    #[test]
    fn winvm_check_argvはskip付きでcheck_desktopを渡す() {
        let argv = build_winvm_argv("relay-winvm", "C:/Hidari/Develop/relay", true, "cargo xtask check-desktop");
        assert_eq!(
            argv,
            vec![
                "run", "--host", "relay-winvm", "--repo", "C:/Hidari/Develop/relay",
                "--skip-when-no-changes", "--", "cargo xtask check-desktop",
            ]
        );
    }

    #[test]
    fn winvm_bundle_argvはskipなし() {
        let argv = build_winvm_argv("relay-winvm", "C:/Hidari/Develop/relay", false, "cargo xtask build-desktop --verbose");
        assert!(!argv.contains(&"--skip-when-no-changes".to_string()));
        assert_eq!(argv.last().unwrap(), "cargo xtask build-desktop --verbose");
    }
}
```

- [ ] **Step 2: 失敗を確認**

Run: `cargo test -p xtask winvm`
Expected: FAIL (`build_winvm_argv` 未定義)

- [ ] **Step 3: winvm_check.rs を薄いラッパーに置換**

ファイル全体を以下に置換:

```rust
//! Mac のローカル変更を Windows 検証 VM (relay-winvm) へ同期し検証する。
//! 実体は generic な PATH 上の `winvm` CLI (windows-vm-verification skill) に委譲する。
//! 設計: dotfiles docs/superpowers/specs/2026-06-26-windows-vm-verification-skill-design.md

use std::process::{Command, ExitCode};

const HOST: &str = "relay-winvm";
const VM_REPO: &str = "C:/Hidari/Develop/relay";

/// ローカル変更を VM へ同期し VM 上で check-desktop を実行 (cfg(windows) 検証)。
pub fn run() -> ExitCode {
    invoke(build_winvm_argv(HOST, VM_REPO, true, "cargo xtask check-desktop"))
}

/// ローカル変更を VM へ同期し VM 上で build-desktop --verbose を実行 (MSI バンドル検証)。
pub fn run_bundle() -> ExitCode {
    invoke(build_winvm_argv(HOST, VM_REPO, false, "cargo xtask build-desktop --verbose"))
}

/// `winvm run` の argv を組み立てる純粋関数。
fn build_winvm_argv(host: &str, repo: &str, skip_when_no_changes: bool, remote_cmd: &str) -> Vec<String> {
    let mut argv = vec![
        "run".to_owned(),
        "--host".to_owned(), host.to_owned(),
        "--repo".to_owned(), repo.to_owned(),
    ];
    if skip_when_no_changes {
        argv.push("--skip-when-no-changes".to_owned());
    }
    argv.push("--".to_owned());
    argv.push(remote_cmd.to_owned());
    argv
}

fn invoke(argv: Vec<String>) -> ExitCode {
    match Command::new("winvm").args(&argv).status() {
        Ok(s) => crate::to_exit_code(s.success()),
        Err(e) => {
            eprintln!(
                "winvm の実行に失敗しました ({e})。windows-vm-verification skill を導入し \
                 `winvm` を PATH に通してください (dotfiles bootstrap)。"
            );
            ExitCode::FAILURE
        }
    }
}
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cargo test -p xtask winvm`
Expected: PASS (2 passed)

- [ ] **Step 5: fmt + 全テスト**

Run: `cargo xtask fmt && cargo test -p xtask`
Expected: 0 警告 / PASS

- [ ] **Step 6: コミット**

```bash
git add crates/xtask/src/winvm_check.rs
git commit -m "refactor: xtask winvm-check/bundle を generic winvm CLI への薄いラッパーに"
```

---

### Task 10: relay doc 更新 + ssh config 差し替え (ローカル)

**Files:**
- Modify: `docs/Windows検証環境構築.md`
- ローカルのみ (非リポ): `~/.ssh/config`、`~/.ssh/relay-winvm-ip.sh`

- [ ] **Step 1: docs/Windows検証環境構築.md を更新**

generic 部分 (IP 解決ロジック・sync の仕組み) は windows-vm-verification skill へ委譲する旨を記し、relay 固有 (host alias `relay-winvm`・repo `C:/Hidari/Develop/relay`・MAC source=`.vmx`) のみ残す。awk resolver の節は削除し、ProxyCommand が `winvm resolve-ip --vmx <path>` を使う形に書き換える。

- [ ] **Step 2: ローカルの ssh config を差し替え (リポ外・手動)**

`~/.ssh/config` の `relay-winvm` の ProxyCommand を変更 (`<VM>` は実 VM バンドルの .vmx パスに置換):
```
  ProxyCommand sh -c 'exec nc "$(winvm resolve-ip --vmx \"$HOME/Virtual Machines.localized/<VM>.vmwarevm/<VM>.vmx\")" 22'
```

- [ ] **Step 3: 動作確認**

Run: `ssh -o BatchMode=yes -o ConnectTimeout=15 relay-winvm "whoami"`
Expected: VM の Windows ユーザ (例 `<DOMAIN>\<user>`) が返る (winvm resolve-ip 経由で接続成立)

- [ ] **Step 4: 旧 awk resolver を退避して撤去**

```bash
mv ~/.ssh/relay-winvm-ip.sh ~/.ssh/relay-winvm-ip.sh.bak
ssh -o BatchMode=yes -o ConnectTimeout=15 relay-winvm "whoami"
```
Expected: まだ成功する (もう awk resolver に依存していない) → 確認後 `rm ~/.ssh/relay-winvm-ip.sh.bak`

- [ ] **Step 5: cargo xtask winvm-check で end-to-end 検証**

Run: `cargo xtask winvm-check`
Expected: VM HEAD 取得 → 同期 → (変更あれば check-desktop) が `winvm` 経由で動く

- [ ] **Step 6: コミット (relay doc のみ)**

```bash
git add docs/Windows検証環境構築.md
git commit -m "docs: Windows検証環境構築を winvm skill 委譲に更新"
```

---

## Self-Review チェック結果

- **Spec coverage:** resolve-ip(Task2)/recover(Task6)/health(Task5)/run(Task3-4)、MAC=.vmx 由来(Task1-2)、env 規約(Task2,4,5)、PATH 化(Task8)、relay 薄いラッパー(Task9)、doc/ssh 差し替え(Task10)、テスト移管(Task3,9) — 全節カバー
- **Placeholder scan:** コード/コマンドは全て具体。SKILL.md/troubleshooting 本文(Task7)のみ散文記述だが構成要素を明示
- **Type consistency:** `files_to_sync`/`to_windows_path`/`resolve_diff_base`/`mkdir_command`/`build_health_powershell`/`find_stale_lock_dirs`/`build_winvm_argv` は定義タスクと利用タスクでシグネチャ一致
