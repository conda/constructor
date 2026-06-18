import sys
from textwrap import dedent

import pytest

from constructor.main import main

_CONSTRUCT = dedent(
    """
    name: test_installer_type_flag
    version: 1.0.0
    installer_type: all
    channels:
      - conda-forge
    specs:
      - ca-certificates
    """
)


def test_dry_run(tmp_path):
    inputfile = dedent(
        """
        name: test_schema_validation
        version: 1.0.0
        installer_type: all
        channels:
          - https://repo.anaconda.com/pkgs/main/
        specs:
          - ca-certificates
        """
    )
    (tmp_path / "construct.yaml").write_text(inputfile)
    main([str(tmp_path), "--dry-run"])


def test_installer_type_flag_valid(tmp_path):
    """Test that --installer-type dont exit with error for valid types."""
    (tmp_path / "construct.yaml").write_text(_CONSTRUCT)
    # No need to test all types
    itype = "exe" if sys.platform.startswith("win") else "sh"
    assert main([str(tmp_path), "--installer-type", itype, "--dry-run"]) is None


def test_installer_type_flag_invalid_for_platform(tmp_path):
    """Test that a type not valid for the current platform/config exits with the expected error message."""
    (tmp_path / "construct.yaml").write_text(_CONSTRUCT)
    # Pick a type that is never valid on this platform.
    bad = "sh" if sys.platform.startswith("win") else "exe"
    with pytest.raises(SystemExit) as exc:
        main([str(tmp_path), "--installer-type", bad, "--dry-run"])
    assert "not available" in str(exc.value)
