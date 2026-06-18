"""Integration tests for :class:`UvWorkspaceLocalityRule`.

Real filesystem (``tmp_path``) projects are built end to end: an offending
source module plus a ``pyproject.toml`` that either declares ``axm-ingot``
as a dependency (importable -> blocking) or omits it entirely (not
importable -> warn-only, CI not broken).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from axm_audit.core.rules.architecture.uv_workspace_locality import (
    UvWorkspaceLocalityRule,
)

pytestmark = pytest.mark.integration

_OFFENDING = (
    "import tomllib\n\n\n"
    "def parse(p):\n"
    "    data = tomllib.loads(p.read_text())\n"
    '    return data["tool"]["uv"]["workspace"]\n'
)


def _make_project(root: Path, *, ingot_dep: bool) -> Path:
    """Build a real project tree with an offending site under *root*."""
    src = root / "src" / "somepkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "mod.py").write_text(_OFFENDING)
    deps = '    "axm-ingot>=0.1",\n' if ingot_dep else ""
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "somepkg"\nversion = "0.1.0"\ndependencies = [\n{deps}]\n'
    )
    return root


def test_forge_site_blocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC4: project with axm-ingot dep + offending site -> blocking."""
    # Force find_spec to miss so the decision relies on the pyproject dep.
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a, **k: None)
    project = _make_project(tmp_path, ingot_dep=True)

    result = UvWorkspaceLocalityRule().check(project)

    assert result.passed is False
    assert result.score < 100
    assert result.details["sites"]


def test_foreign_workspace_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC4: project WITHOUT axm-ingot + offending site -> warn-only.

    ``passed`` stays True so a foreign workspace's CI is not broken.
    """
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a, **k: None)
    project = _make_project(tmp_path, ingot_dep=False)

    result = UvWorkspaceLocalityRule().check(project)

    assert result.passed is True
    assert result.score == 100
    assert result.details["sites"]
