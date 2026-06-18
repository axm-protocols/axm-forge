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


def _make_project(
    root: Path, *, offending: bool = True, ingot_dep: bool = False
) -> Path:
    """Build a real project tree under *root*.

    *offending* selects an offending workspace-parsing module vs. a clean one;
    *ingot_dep* declares ``axm-ingot`` as a dependency in the pyproject (so the
    importability decision can rely on the declared dep when ``find_spec`` is
    forced to miss).
    """
    src = root / "src" / "somepkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    body = _OFFENDING if offending else "def clean():\n    return 1\n"
    (src / "mod.py").write_text(body)
    deps = '    "axm-ingot>=0.1",\n' if ingot_dep else ""
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "somepkg"\nversion = "0.1.0"\ndependencies = [\n{deps}]\n'
    )
    return root


@pytest.fixture
def rule() -> UvWorkspaceLocalityRule:
    """Return a fresh rule instance."""
    return UvWorkspaceLocalityRule()


def test_forge_site_blocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC4: project with axm-ingot dep + offending site -> blocking."""
    # Force find_spec to miss so the decision relies on the pyproject dep.
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a, **k: None)
    project = _make_project(tmp_path, ingot_dep=True)

    result = UvWorkspaceLocalityRule().check(project)

    assert result.passed is False
    assert result.score < 100
    assert result.details["sites"]


def test_blocking_when_ingot_importable(
    rule: UvWorkspaceLocalityRule,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: offending site + ingot importable -> blocking (passed=False)."""
    project = _make_project(tmp_path, offending=True)
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name, *a, **k: object() if name == "axm_ingot" else None,
    )

    result = rule.check(project)

    assert result.passed is False
    assert result.score < 100
    assert result.details["sites"]


def test_clean_project_passes(
    rule: UvWorkspaceLocalityRule,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: no offending site -> passed with zero finding."""
    project = _make_project(tmp_path, offending=False)
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name, *a, **k: object() if name == "axm_ingot" else None,
    )

    result = rule.check(project)

    assert result.passed is True
    assert result.score == 100
    assert result.details["sites"] == []


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


def test_warn_only_when_ingot_absent(
    rule: UvWorkspaceLocalityRule,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2, AC3: offending site + ingot NOT importable -> warn-only.

    The site is still surfaced in ``details`` and the message carries an
    actionable note that ``axm-ingot`` is not importable here.
    """
    project = _make_project(tmp_path, offending=True)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a, **k: None)

    result = rule.check(project)

    assert result.passed is True
    assert result.score == 100
    assert result.details["sites"]
    note = (
        result.message + str(result.text or "") + str(result.fix_hint or "")
    ).lower()
    assert "importable" in note


_FAULTY_GET_CHAIN = (
    "import tomllib\n\n\n"
    "def resolve(data: dict) -> dict:\n"
    '    return data.get("tool", {}).get("uv", {}).get("workspace", {})\n'
)
_CLEAN = "def add(a: int, b: int) -> int:\n    return a + b\n"


def _make_multimodule_project(tmp_path: Path) -> Path:
    """Single-package project with a faulty (bad.py) and a clean (good.py) module."""
    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "bad.py").write_text(_FAULTY_GET_CHAIN, encoding="utf-8")
    (pkg / "good.py").write_text(_CLEAN, encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\nversion = "0.1"\n', encoding="utf-8"
    )
    return tmp_path


def test_check_flags_faulty_module(tmp_path: Path) -> None:
    """AC1,AC2: the rule check() reports the faulty module with file + line."""
    project = _make_multimodule_project(tmp_path)

    result = UvWorkspaceLocalityRule().check(project)

    assert result.passed is False
    assert result.details is not None
    sites = result.details["sites"]
    assert isinstance(sites, list)
    files = {str(s["file"]) for s in sites}
    assert any("bad.py" in f for f in files)
    assert all("good.py" not in f for f in files)
    assert "axm_ingot.uv.resolve_workspace" in (result.fix_hint or "")


def test_ingot_module_is_exempt(tmp_path: Path) -> None:
    """AC3: the same faulty source under axm_ingot/ produces no finding."""
    ingot = tmp_path / "src" / "axm_ingot"
    ingot.mkdir(parents=True)
    (ingot / "__init__.py").write_text("", encoding="utf-8")
    (ingot / "uv.py").write_text(_FAULTY_GET_CHAIN, encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "axm-ingot"\nversion = "0.1"\n', encoding="utf-8"
    )

    result = UvWorkspaceLocalityRule().check(tmp_path)

    assert result.passed is True
    assert result.details is not None
    assert result.details["sites"] == []
