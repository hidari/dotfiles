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
