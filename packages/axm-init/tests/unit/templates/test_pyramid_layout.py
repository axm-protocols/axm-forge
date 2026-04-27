"""Unit tests: scaffold templates declare the 3-level test pyramid.

Reads template files directly — no Copier invocation, no subprocess, no network.
Replaces the slower integration tests that scaffolded a full project just to
assert static template content.
"""

from __future__ import annotations

from pathlib import Path

import pytest

TEMPLATES_ROOT = Path(__file__).resolve().parents[3] / "src" / "axm_init" / "templates"

# Templates that produce a *package* (and therefore must ship the pyramid).
# `uv-workspace` is excluded: it scaffolds the workspace shell, not a package.
PACKAGE_TEMPLATES = ("python-project", "workspace-member")


@pytest.mark.parametrize("template", PACKAGE_TEMPLATES)
@pytest.mark.parametrize("level", ("unit", "integration", "e2e"))
def test_template_ships_pyramid_level(template: str, level: str) -> None:
    level_dir = TEMPLATES_ROOT / template / "tests" / level
    assert level_dir.is_dir(), f"{template}: tests/{level}/ missing"
    assert (level_dir / "__init__.py").is_file(), (
        f"{template}: tests/{level}/__init__.py missing"
    )
    assert (level_dir / "conftest.py").is_file(), (
        f"{template}: tests/{level}/conftest.py missing"
    )


@pytest.mark.parametrize("template", PACKAGE_TEMPLATES)
def test_template_ships_starter_version_test(template: str) -> None:
    starter = TEMPLATES_ROOT / template / "tests" / "unit" / "test_version.py.jinja"
    assert starter.is_file(), f"{template}: starter test_version.py.jinja missing"


@pytest.mark.parametrize("template", PACKAGE_TEMPLATES)
def test_pyproject_declares_pyramid_markers(template: str) -> None:
    pyproject = (TEMPLATES_ROOT / template / "pyproject.toml.jinja").read_text()
    assert "markers = [" in pyproject, f"{template}: no markers block"
    assert "integration:" in pyproject, f"{template}: integration marker missing"
    assert "e2e:" in pyproject, f"{template}: e2e marker missing"
