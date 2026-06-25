#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""windows-vm-verification: VMware Fusion 上の Windows VM を繋ぐ/直す/調べる/検証する generic CLI。"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


def extract_mac_from_vmx(vmx_text: str) -> str | None:
    """`.vmx` 本文から NIC MAC を小文字で返す (generatedAddress 優先、無ければ address)。"""
    for key in ("ethernet0.generatedAddress", "ethernet0.address"):
        m = re.search(rf'^\s*{re.escape(key)}\s*=\s*"([^"]+)"', vmx_text, re.MULTILINE)
        if m:
            return m.group(1).strip().lower()
    return None


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


DEFAULT_LEASES = "/var/db/vmware/vmnet-dhcpd-vmnet8.leases"


def _env_or(arg_value: str | None, env_key: str, default: str | None = None) -> str | None:
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


def files_to_sync(branch_delta: str, working_delta: str, untracked: str) -> list[str]:
    """行をトリム/空行除去/重複排除/安定ソート."""
    s: set[str] = set()
    for block in (branch_delta, working_delta, untracked):
        for line in block.splitlines():
            t = line.strip()
            if t:
                s.add(t)
    return sorted(s)


def to_windows_path(path: str) -> str:
    r"""`/` を `\` に変換."""
    return path.replace("/", "\\")


def resolve_diff_base(vm_head: str, vm_head_known: bool, fallback: str) -> str:
    """vm_head_known なら vm_head を返す、さもなければ fallback を返す."""
    return vm_head if vm_head_known else fallback


def mkdir_command(repo_win: str, files: list[str]) -> str | None:
    """親ディレクトリを dedup し `if not exist ... mkdir ...` を ` & ` 連結。直下のみなら `None`."""
    parents = set()
    for f in files:
        parent = str(Path(f).parent)
        if parent and parent != ".":
            parents.add(f"{repo_win}\\{to_windows_path(parent)}")
    if not parents:
        return None
    return " & ".join(f'if not exist "{p}" mkdir "{p}"' for p in sorted(parents))


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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="winvm", description="VMware Fusion Windows VM ops/verify")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("resolve-ip", help="VMware NAT lease から VM の現 IP を解決")
    sp.add_argument("--vmx")
    sp.add_argument("--leases")
    sp.set_defaults(func=cmd_resolve_ip)

    rp = sub.add_parser("run", help="git 差分を scp 同期して remote コマンド実行")
    rp.add_argument("--host")
    rp.add_argument("--repo")
    rp.add_argument("--base")
    rp.add_argument("--skip-when-no-changes", action="store_true")
    rp.add_argument("remote", nargs=argparse.REMAINDER, help="-- の後に remote コマンド")
    rp.set_defaults(func=cmd_run)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
