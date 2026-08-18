import json

import pytest
from conda.base.context import context
from conda.common.path.python import get_python_site_packages_short_path
from conda.core.prefix_data import PrefixData
from conda.models.records import PackageRecord, PrefixRecord

from constructor.build_outputs import get_build_env_records

# Match the current platform, since tests run on multiple platforms
SUBDIR = context.subdir


def _make_package_record(name, version="1.2.3", build_number=0):
    """Make a dummy package record for test fixtures."""
    return PackageRecord(
        name=name,
        version=version,
        build=str(build_number),
        build_number=build_number,
        channel=None,
        subdir=SUBDIR,
        fn=f"{name}-{version}-{build_number}.conda",
    )


def _fake_prefix_data(tmp_path, records):
    """Build a PrefixData whose in-memory records are injected directly,
    so no conda-meta files are ever written to disk. Approach adapted from
    conda/conda/testing/helpers.py::_get_solver_base, which patches the
    same private `__prefix_records` attribute for the same reason."""
    prefix_data = PrefixData(str(tmp_path))
    prefix_data._PrefixData__prefix_records = {
        rec.name: PrefixRecord.from_objects(rec) for rec in records
    }
    return prefix_data


@pytest.fixture
def patch_prefix_data(monkeypatch):
    """Patch constructor.build_outputs.PrefixData so get_build_env_records()
    returns records we control, without touching disk."""

    def _patch(records):
        # Replace PrefixData itself with this function, so calling
        # PrefixData(prefix) returns our fake object instead of reading
        # real conda-meta files. Reuse the same fake per prefix instead of
        # building a new one each call.
        fake_instances = {}

        def _fake_prefix_data_for(prefix, **kwargs):
            if prefix not in fake_instances:
                fake_instances[prefix] = _fake_prefix_data(prefix, records)
            return fake_instances[prefix]

        monkeypatch.setattr("constructor.build_outputs.PrefixData", _fake_prefix_data_for)

    return _patch


@pytest.mark.parametrize(
    "records",
    [
        pytest.param([], id="empty-environment"),
        pytest.param([_make_package_record("numpy")], id="single-package"),
        pytest.param(
            [
                _make_package_record("numpy"),
                _make_package_record("foobar", version="24.11.0"),
            ],
            id="multiple-packages",
        ),
    ],
)
def test_get_build_env_records_with_explicit_prefix(tmp_path, patch_prefix_data, records):
    patch_prefix_data(records)

    result = get_build_env_records(prefix=str(tmp_path))

    assert sorted(rec["name"] for rec in result) == sorted(rec.name for rec in records)
    assert all(isinstance(rec, dict) for rec in result)


def test_get_build_env_records_defaults_to_active_environment(
    monkeypatch, tmp_path, patch_prefix_data
):
    """When prefix is not given, it must fall back to conda.exports.default_prefix
    (the environment currently running constructor), not construct.yaml's
    unrelated 'default_prefix' install-location setting."""
    monkeypatch.setattr("constructor.build_outputs.default_prefix", str(tmp_path))
    patch_prefix_data([_make_package_record("foobar", version="24.11.0")])

    result = get_build_env_records()

    assert [rec["name"] for rec in result] == ["foobar"]


def test_get_build_env_records_includes_pip_installed_packages(tmp_path):
    """Verify also pip packages are included among build environment deps."""
    meta_dir = tmp_path / "conda-meta"
    meta_dir.mkdir()

    # Mock a conda package and a package installed via pip
    python_record = PrefixRecord(
        name="python",
        version="1.2.3",
        build="0",
        build_number=0,
        channel=None,
        subdir=SUBDIR,
        fn="python-1.2.3-0.conda",
        paths_data={"paths": [], "paths_version": 1},
        files=[],
    )
    (meta_dir / "python-1.2.3-0.json").write_text(json.dumps(python_record.dump()))

    site_packages = tmp_path / get_python_site_packages_short_path("1.2")
    site_packages.mkdir(parents=True)
    dist_info = site_packages / "fakepkg-1.0.0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text("Metadata-Version: 2.1\nName: fakepkg\nVersion: 1.0.0\n")
    (dist_info / "INSTALLER").write_text("pip\n")
    (dist_info / "RECORD").write_text("")

    result = get_build_env_records(prefix=str(tmp_path))

    assert sorted(rec["name"] for rec in result) == ["fakepkg", "python"]
    python_rec = next(rec for rec in result if rec["name"] == "python")
    assert "files" not in python_rec
    assert "paths_data" not in python_rec
