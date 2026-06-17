"""Integration tests for UvWorkspaceLocalityRule — real-filesystem fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_FAULTY = (
    "import tomllib\n\n\n"
    "def resolve(data: dict) -> dict:\n"
    '    return data.get("tool", {}).get("uv", {}).get("workspace", {})\n'
)

_CLEAN = "def add(a: int, b: int) -> int:\n    return a + b\n"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _mk_project(tmp_path: Path) -> Path:
    """Create a minimal single-package project with a faulty + clean module."""
    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    _write(pkg / "bad.py", _FAULTY)
    _write(pkg / "good.py", _CLEAN)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\nversion = "0.1"\n', encoding="utf-8"
    )
    return tmp_path


def test_check_flags_faulty_module(tmp_path: Path) -> None:
    """AC1,AC2: the rule check() reports the faulty module with file + line."""
    from axm_audit.core.rules.architecture.uv_workspace_locality import (
        UvWorkspaceLocalityRule,
    )

    project = _mk_project(tmp_path)

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
    from axm_audit.core.rules.architecture.uv_workspace_locality import (
        UvWorkspaceLocalityRule,
    )

    ingot = tmp_path / "src" / "axm_ingot"
    ingot.mkdir(parents=True)
    (ingot / "__init__.py").write_text("", encoding="utf-8")
    _write(ingot / "uv.py", _FAULTY)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "axm-ingot"\nversion = "0.1"\n', encoding="utf-8"
    )

    result = UvWorkspaceLocalityRule().check(tmp_path)

    assert result.passed is True
    assert result.details is not None
    assert result.details["sites"] == []


def test_rule_runs_via_audit_category(tmp_path: Path) -> None:
    """AC1,AC4: the architecture category surfaces the faulty module."""
    from axm_audit.core.auditor import audit_project

    project = _mk_project(tmp_path)

    result = audit_project(project, category="architecture")

    locality = next(
        (c for c in result.checks if c.rule_id == "ARCH_UV_WORKSPACE_LOCALITY"),
        None,
    )
    assert locality is not None, "the locality rule must run under architecture"
    assert locality.passed is False
    assert locality.details is not None
    files = {str(s["file"]) for s in locality.details["sites"]}
    assert any("bad.py" in f for f in files)
