import winvm

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


def test_parse_latest_lease_ip_returns_latest_matching_block():
    assert winvm.parse_latest_lease_ip(LEASES, "00:0c:29:b0:ea:5a") == "172.16.237.129"


def test_parse_latest_lease_ip_is_case_insensitive_on_mac():
    assert winvm.parse_latest_lease_ip(LEASES, "00:0C:29:BB:8B:20") == "172.16.237.130"


def test_parse_latest_lease_ip_returns_none_when_no_match():
    assert winvm.parse_latest_lease_ip(LEASES, "de:ad:be:ef:00:00") is None


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


def test_remote_reset_command():
    assert winvm.remote_reset_command("C:\\repo") == (
        'cd /d "C:\\repo" && git checkout -- . && git clean -fd'
    )
    # parameterization (negative case): different repo path -> different, correct output (not hardcoded)
    assert winvm.remote_reset_command("D:\\other") == (
        'cd /d "D:\\other" && git checkout -- . && git clean -fd'
    )


def test_remote_exec_command():
    assert winvm.remote_exec_command("C:\\repo", "cargo xtask check-desktop") == (
        'cd /d "C:\\repo" && cargo xtask check-desktop'
    )
    assert winvm.remote_exec_command("D:\\other", "echo hi") == 'cd /d "D:\\other" && echo hi'


def test_build_health_powershell_includes_encoding_and_tools():
    ps = winvm.build_health_powershell(["node", "cargo"], "C:/proj/app")
    assert "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8" in ps
    assert "fsutil dirty query C:" in ps
    assert "'node'" in ps and "'cargo'" in ps
    assert "C:/proj/app" in ps


def test_build_health_powershell_no_repo_omits_repo_section():
    ps = winvm.build_health_powershell(["node"], None)
    assert "repo state" not in ps


