from constructor.preconda import write_condarc


def test_write_condarc_with_condarc_dict(tmp_path):
    """Test that write_condarc creates .condarc file when condarc is a dict."""
    info = {"condarc": {"channels": ["conda-forge"], "ssl_verify": False}}
    write_condarc(info, str(tmp_path))

    condarc_file = tmp_path / ".condarc"
    assert condarc_file.exists()
    content = condarc_file.read_text()
    assert "channels:" in content
    assert "conda-forge" in content
    assert "ssl_verify:" in content


def test_write_condarc_with_condarc_string(tmp_path):
    """Test that write_condarc creates .condarc file when condarc is a string."""
    info = {"condarc": "channels:\n  - my-channel\nssl_verify: false\n"}
    write_condarc(info, str(tmp_path))

    condarc_file = tmp_path / ".condarc"
    assert condarc_file.exists()
    content = condarc_file.read_text()
    assert "channels:" in content
    assert "my-channel" in content
    assert "ssl_verify:" in content


def test_write_condarc_with_write_condarc_flag(tmp_path):
    """Test legacy write_condarc=True approach."""
    info = {
        "write_condarc": True,
        "channels": ["defaults"],
    }
    write_condarc(info, str(tmp_path))

    condarc_file = tmp_path / ".condarc"
    assert condarc_file.exists()
    assert "defaults" in condarc_file.read_text()


def test_write_condarc_no_content_no_file(tmp_path):
    """Test that write_condarc does nothing when no condarc is configured."""
    info = {}
    write_condarc(info, str(tmp_path))

    condarc_file = tmp_path / ".condarc"
    assert not condarc_file.exists()


def test_write_condarc_write_condarc_without_channels(tmp_path):
    """Test that write_condarc does nothing when write_condarc=True but no channels."""
    info = {"write_condarc": True}
    write_condarc(info, str(tmp_path))

    condarc_file = tmp_path / ".condarc"
    assert not condarc_file.exists()
