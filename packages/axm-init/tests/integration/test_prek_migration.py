"""Integration: templates migrated from pre-commit to prek (AXM-2056).

These tests read the real template files shipped under ``axm_init.templates``
via ``get_template_path`` (real I/O on the packaged template tree) and assert on
their content, so a future drift back to ``pre-commit`` fails here. They cover
the template *source*; the scaffolded-output behaviour is covered in
``test_scaffold_flow_via_cli.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.core.templates import TemplateType, get_template_path

pytestmark = pytest.mark.integration


def _read(template: TemplateType, *parts: str) -> str:
    """Read a file from the packaged *template* tree as text."""
    path = Path(get_template_path(template)).joinpath(*parts)
    return path.read_text()


def test_standalone_pyproject_pins_prek() -> None:
    """AC1: python-project dev deps pin prek>=0.4.4, not pre-commit."""
    content = _read(TemplateType.STANDALONE, "pyproject.toml.jinja")
    assert '"prek>=0.4.4"' in content
    assert "pre-commit" not in content


def test_standalone_copier_installs_prek() -> None:
    """AC1: python-project copier tasks add prek and run prek install."""
    content = _read(TemplateType.STANDALONE, "copier.yml")
    assert "uv run prek install" in content
    assert " prek " in content  # `uv add --group dev ... prek ...`
    assert "pre-commit" not in content


def test_workspace_pyproject_pins_prek() -> None:
    """AC2: uv-workspace dev deps pin prek>=0.4.4, not pre-commit."""
    content = _read(TemplateType.WORKSPACE, "pyproject.toml.jinja")
    assert '"prek>=0.4.4"' in content
    assert "pre-commit" not in content


def test_workspace_copier_installs_prek() -> None:
    """AC2: uv-workspace copier task runs prek install."""
    content = _read(TemplateType.WORKSPACE, "copier.yml")
    assert "uv run prek install" in content
    assert "pre-commit" not in content


def test_workspace_contributing_mentions_prek() -> None:
    """AC2: uv-workspace CONTRIBUTING.md says `uv run prek install`."""
    content = _read(TemplateType.WORKSPACE, "CONTRIBUTING.md.jinja")
    assert "uv run prek install" in content
    assert "pre-commit" not in content


def test_member_pyproject_pins_prek() -> None:
    """AC3: workspace-member dev deps pin prek>=0.4.4 (only surface)."""
    content = _read(TemplateType.MEMBER, "pyproject.toml.jinja")
    assert '"prek>=0.4.4"' in content
    assert "pre-commit" not in content


@pytest.mark.parametrize(
    "template",
    [
        pytest.param(TemplateType.STANDALONE, id="standalone"),
        pytest.param(TemplateType.WORKSPACE, id="workspace"),
    ],
)
def test_dependabot_references_prek(template: TemplateType) -> None:
    """AC5: dependabot.yml (when present) references prek, not pre-commit."""
    path = Path(get_template_path(template)) / ".github" / "dependabot.yml"
    if not path.is_file():
        pytest.skip("no dependabot.yml in this template")
    content = path.read_text()
    assert "pre-commit" not in content


@pytest.mark.parametrize(
    "template",
    [
        pytest.param(TemplateType.STANDALONE, id="standalone"),
        pytest.param(TemplateType.WORKSPACE, id="workspace"),
    ],
)
def test_autoupdate_workflow_uses_prek(template: TemplateType) -> None:
    """AC5: pre-commit-autoupdate.yml uses prek autoupdate via uv tool install."""
    content = _read(template, ".github", "workflows", "pre-commit-autoupdate.yml")
    assert "uv tool install prek" in content
    assert "prek autoupdate" in content
    assert "pip install pre-commit" not in content
    assert "pre-commit autoupdate" not in content


@pytest.mark.parametrize(
    "template",
    [
        pytest.param(TemplateType.STANDALONE, id="standalone"),
        pytest.param(TemplateType.WORKSPACE, id="workspace"),
    ],
)
def test_precommit_config_template_source_is_jinja(template: TemplateType) -> None:
    """AC4/AC6: template SOURCE is .pre-commit-config.yaml.jinja, not literal."""
    root = Path(get_template_path(template))
    assert (root / ".pre-commit-config.yaml.jinja").is_file()
    assert not (root / ".pre-commit-config.yaml").exists()
