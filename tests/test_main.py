import sys
from textwrap import dedent

import pytest
from conda.models.version import VersionOrder

from constructor._types import InstallerTypes
from constructor.main import main, validate_frozen_envs
from constructor.utils import StandaloneExeType

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
    itype = InstallerTypes.EXE if sys.platform.startswith("win") else InstallerTypes.SH
    assert main([str(tmp_path), "--installer-type", itype, "--dry-run"]) is None


def test_installer_type_flag_invalid_for_platform(tmp_path):
    """Test that a type not valid for the current platform/config exits with the expected error message."""
    (tmp_path / "construct.yaml").write_text(_CONSTRUCT)
    # Pick a type that is never valid on this platform.
    bad = InstallerTypes.SH if sys.platform.startswith("win") else InstallerTypes.EXE
    with pytest.raises(SystemExit) as exc:
        main([str(tmp_path), "--installer-type", bad, "--dry-run"])
    assert "invalid installer type" in str(exc.value)


@pytest.mark.parametrize(
    ("exe_type", "exe_version", "error"),
    [
        pytest.param(StandaloneExeType.CONDA, "25.4.0", False, id="before-affected-range"),
        pytest.param(StandaloneExeType.CONDA, "25.5.0", True, id="start-of-affected-range"),
        pytest.param(StandaloneExeType.CONDA, "25.6.1", True, id="within-affected-range"),
        pytest.param(StandaloneExeType.CONDA, "25.7.0", False, id="end-of-affected-range"),
        pytest.param(StandaloneExeType.CONDA, "25.8.0", False, id="after-affected-range"),
        pytest.param(StandaloneExeType.MAMBA, "25.6.0", False, id="micromamba-unaffected"),
        pytest.param(None, None, False, id="unidentified-unaffected"),
    ],
)
def test_validate_frozen_envs_conda_standalone_versions(exe_type, exe_version, error):
    info = {"freeze_base": {"conda": "defaults"}}
    version = VersionOrder(exe_version) if exe_version else None

    if error:
        with pytest.raises(RuntimeError, match="conda-standalone 25.5.x"):
            validate_frozen_envs(info, exe_type, version)
    else:
        validate_frozen_envs(info, exe_type, version)
