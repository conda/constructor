from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from constructor.conda_interface import cc_platform
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
