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

