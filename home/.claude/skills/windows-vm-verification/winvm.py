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
