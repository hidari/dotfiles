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

