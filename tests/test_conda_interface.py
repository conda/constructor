import pytest
from conda.base.context import context
from conda.core.prefix_data import PrefixData
from conda.models.records import PackageRecord, PrefixRecord

from constructor.conda_interface import get_build_env_records

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
    """Patch constructor.conda_interface.PrefixData so get_build_env_records()
    returns records we control, without touching disk."""

    def _patch(records):
        # Replace PrefixData itself with this function, so calling
        # PrefixData(prefix) returns our fake object instead of reading
        # real conda-meta files. Reuse the same fake per prefix instead of
        # building a new one each call.
        fake_instances = {}

        def _fake_prefix_data_for(prefix):
            if prefix not in fake_instances:
                fake_instances[prefix] = _fake_prefix_data(prefix, records)
            return fake_instances[prefix]

        monkeypatch.setattr("constructor.conda_interface.PrefixData", _fake_prefix_data_for)

    return _patch


@pytest.mark.parametrize(
    "records",
    [
        pytest.param([], id="empty-environment"),
        pytest.param([_make_package_record("numpy")], id="single-package"),
        pytest.param(
            [
                _make_package_record("numpy"),
                _make_package_record("conda-standalone", version="24.11.0"),
            ],
            id="multiple-packages",
        ),
    ],
)
def test_get_build_env_records_with_explicit_prefix(tmp_path, patch_prefix_data, records):
    patch_prefix_data(records)

    result = get_build_env_records(prefix=str(tmp_path))

    assert sorted(rec.name for rec in result) == sorted(rec.name for rec in records)


def test_get_build_env_records_defaults_to_active_environment(
    monkeypatch, tmp_path, patch_prefix_data
):
    """When prefix is not given, it must fall back to conda.exports.default_prefix
    (the environment currently running constructor), not construct.yaml's
    unrelated 'default_prefix' install-location setting."""
    monkeypatch.setattr("constructor.conda_interface.default_prefix", str(tmp_path))
    patch_prefix_data([_make_package_record("conda-standalone", version="24.11.0")])

    result = get_build_env_records()

    assert [rec.name for rec in result] == ["conda-standalone"]
