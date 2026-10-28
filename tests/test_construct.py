from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from constructor.conda_interface import SUPPORTED_PLATFORMS, cc_platform
from constructor.construct import ns_platform
from constructor.construct import parse as construct_parse
from constructor.construct import render as construct_render

if TYPE_CHECKING:
    from pathlib import Path


CONSTRUCT_YAML = """\
name: Installer
version: 1.0.0
specs:
  - python
  - miniforge_console_shortcut  # [win]
"""

CONSTRUCT_YAML_JINJA = """\
name: Installer
version: 1.0.0
specs:
  - python
{%- if os.environ.get("__CONSTRUCTOR_INCLUDE_CONDA__") %}
  - conda
{%- endif %}
"""

CONSTRUCY_YAML_BROKEN = """\
name: Installer
version: 1.0.0
specs
"""


@pytest.fixture
def construct_yaml_file(tmp_path: Path) -> str:
    file_path = tmp_path / "construct.yaml"
    file_path.write_text(CONSTRUCT_YAML)
    return str(file_path)


@pytest.fixture
def construct_yaml_file_jinja(tmp_path: Path) -> str:
    file_path = tmp_path / "construct.yaml"
    file_path.write_text(CONSTRUCT_YAML_JINJA)
    return str(file_path)


@pytest.mark.parametrize("platform", ("linux-64", "win-64"))
def test_render(platform: str, construct_yaml_file: Path):
    rendered = construct_render(construct_yaml_file, platform)
    rendered_lines = rendered.splitlines()
    expected = CONSTRUCT_YAML.splitlines()[:-1]
    if platform == "win-64":
        expected.append("  - miniforge_console_shortcut")
    assert rendered_lines == expected


@pytest.mark.parametrize("platform", ("linux-64", "win-64"))
def test_parse(platform: str, construct_yaml_file: Path):
    parsed = construct_parse(construct_yaml_file, platform)
    assert parsed["name"] == "Installer"
    assert parsed["version"] == "1.0.0"
    expected_specs = [
        "python",
        *(("miniforge_console_shortcut",) if platform == "win-64" else ()),
    ]
    assert parsed["specs"] == expected_specs


@pytest.mark.parametrize("include_conda", (True, False))
def test_render_jinja(
    include_conda: bool, construct_yaml_file_jinja: Path, monkeypatch: pytest.MonkeyPatch
):
    if include_conda:
        monkeypatch.setenv("__CONSTRUCTOR_INCLUDE_CONDA__", "1")
    rendered = construct_render(construct_yaml_file_jinja, cc_platform)
    rendered_lines = rendered.splitlines()
    expected = CONSTRUCT_YAML_JINJA.splitlines()[:-3]
    if include_conda:
        expected.append("  - conda")
    assert rendered_lines == expected


@pytest.mark.parametrize("include_conda", (True, False))
def test_parse_jinja(
    include_conda: bool, construct_yaml_file_jinja: Path, monkeypatch: pytest.MonkeyPatch
):
    if include_conda:
        monkeypatch.setenv("__CONSTRUCTOR_INCLUDE_CONDA__", "1")
    parsed = construct_parse(construct_yaml_file_jinja, cc_platform)
    assert parsed["name"] == "Installer"
    assert parsed["version"] == "1.0.0"
    expected_specs = [
        "python",
        *(("conda",) if include_conda else ()),
    ]
    assert parsed["specs"] == expected_specs


def test_parse_error(tmp_path):
    construct_yaml_file = tmp_path / "construct.yaml"
    construct_yaml_file.write_text(CONSTRUCY_YAML_BROKEN)
    with pytest.raises(SystemExit) as exc:
        construct_parse(construct_yaml_file, cc_platform)
    assert exc.value.code != 0
    assert "Unable to parse" in str(exc.getrepr())


NS_PLATFORM_TRUE_FLAGS = {
    "linux-64": {"linux", "linux64", "x86", "x86_64", "unix"},
    "linux-aarch64": {"linux", "aarch64", "unix"},
    "linux-ppc64le": {"linux", "ppc64le", "unix"},
    "linux-s390x": {"linux", "s390x", "unix"},
    "linux-riscv64": {"linux", "riscv64", "unix"},
    "win-64": {"x86", "x86_64", "win", "win64"},
    "win-arm64": {"win", "win_arm64"},
    "osx-64": {"x86", "x86_64", "osx", "unix"},
    "osx-arm64": {"arm64", "osx", "unix"},
}


@pytest.mark.parametrize("platform", SUPPORTED_PLATFORMS)
def test_ns_platform(platform):
    result = ns_platform(platform)
    assert result
    true_flags = NS_PLATFORM_TRUE_FLAGS[platform]
    for flag, value in result.items():
        assert value is (flag in true_flags), f"{platform}: expected {flag}={flag in true_flags}"


def test_select_lines_preserves_comment_only_lines():
    """Comment-only lines must survive select_lines().

    ``select_lines`` used to drop every line whose first non-space character
    was ``#``. Inside a YAML block scalar (``|`` or ``>``) such a line is
    literal string content, not a comment, so dropping it corrupted the
    rendered file -- e.g. a ``condarc: |`` value in ``construct.yaml`` lost
    its comment lines and the result no longer parsed as the author wrote it.
    """
    from constructor.construct import select_lines

    data = """\
condarc: |
  # This config file should be located in `C:\\Python\\Miniforge3\\.condarc`.
  #
  # There is another config file in `C:\\ProgramData\\conda\\condarc.d`.
  #
allow_other_channels: yes
report_errors: no
"""
    result = select_lines(data, {})
    assert "# This config file should be located in `C:\\Python\\Miniforge3\\.condarc`." in result
    assert "# There is another config file in `C:\\ProgramData\\conda\\condarc.d`." in result
    # Non-comment content is untouched.
    assert "allow_other_channels: yes" in result
    assert "report_errors: no" in result


def test_select_lines_preserves_top_level_comments():
    """Comments outside a block scalar are preserved too.

    They are valid YAML and dropping them loses information for anyone
    reading the generated file.
    """
    from constructor.construct import select_lines

    data = """\
# a leading comment
name: example
version: "1.0"
"""
    result = select_lines(data, {})
    assert "# a leading comment" in result
    assert "name: example" in result
