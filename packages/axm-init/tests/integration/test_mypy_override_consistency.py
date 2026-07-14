from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from axm_init.tools.scaffold import InitScaffoldTool

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PACKAGES = _REPO_ROOT / "packages"


def _load_mypy(pyproject: Path) -> dict[str, object] | None:
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    tool = data.get("tool", {})
    mypy = tool.get("mypy") if isinstance(tool, dict) else None
    return mypy if isinstance(mypy, dict) else None


def _is_strict(mypy: dict[str, object]) -> bool:
    return (
        mypy.get("disallow_untyped_defs") is True
        and mypy.get("disallow_incomplete_defs") is True
    )


def _tests_override(mypy: dict[str, object]) -> dict[str, object] | None:
    overrides = mypy.get("overrides", [])
    if not isinstance(overrides, list):
        return None
    for override in overrides:
        if not isinstance(override, dict):
            continue
        module = override.get("module")
        modules = [module] if isinstance(module, str) else module
        if isinstance(modules, list) and "tests.*" in modules:
            return override
    return None


def _strict_members() -> list[tuple[str, dict[str, object]]]:
    members: list[tuple[str, dict[str, object]]] = []
    for pyproject in sorted(_PACKAGES.glob("*/pyproject.toml")):
        mypy = _load_mypy(pyproject)
        if mypy is not None and _is_strict(mypy):
            members.append((pyproject.parent.name, mypy))
    return members


def test_every_strict_member_tests_override_relaxes_incomplete_defs() -> None:
    strict = _strict_members()
    assert strict, "expected at least one strict forge member"
    offenders = []
    for name, mypy in strict:
        override = _tests_override(mypy)
        if override is None or override.get("disallow_incomplete_defs") is not False:
            offenders.append(name)
    assert offenders == [], (
        f"strict members lacking tests.* disallow_incomplete_defs = false: {offenders}"
    )


def test_no_strict_member_missing_tests_override() -> None:
    strict = _strict_members()
    missing = [name for name, mypy in strict if _tests_override(mypy) is None]
    assert missing == [], f"strict members without a tests.* override: {missing}"


# --- freshly rendered templates (via InitScaffoldTool) ---


def _scaffold_standalone(tmp_path: Path) -> Path:
    """Render the python-project template into tmp_path; return its pyproject."""
    dest = tmp_path / "demo-pkg"
    dest.mkdir()
    result = InitScaffoldTool().execute(
        path=str(dest),
        org="DemoOrg",
        author="Demo Author",
        email="demo@example.com",
        license="MIT",
        description="demo package",
    )
    assert result.success, result.error
    return dest / "pyproject.toml"


def _scaffold_member(tmp_path: Path) -> Path:
    """Render the workspace-member template inside a fresh workspace."""
    tool = InitScaffoldTool()
    ws = tmp_path / "demo-ws"
    ws.mkdir()
    ws_result = tool.execute(
        path=str(ws),
        org="DemoOrg",
        author="Demo Author",
        email="demo@example.com",
        license="MIT",
        description="demo workspace",
        workspace=True,
    )
    assert ws_result.success, ws_result.error
    member_result = tool.execute(
        path=str(ws),
        member="demo-member",
        org="DemoOrg",
        author="Demo Author",
        email="demo@example.com",
        license="MIT",
        description="demo member",
    )
    assert member_result.success, member_result.error
    return ws / "packages" / "demo-member" / "pyproject.toml"


def test_rendered_python_project_relaxes_incomplete_defs(tmp_path: Path) -> None:
    """Freshly rendered python-project relaxes incomplete defs (AC4)."""
    mypy = _load_mypy(_scaffold_standalone(tmp_path))
    assert mypy is not None
    override = _tests_override(mypy)
    assert override is not None
    assert override.get("disallow_incomplete_defs") is False


def test_rendered_workspace_member_relaxes_incomplete_defs(tmp_path: Path) -> None:
    """Freshly rendered workspace-member relaxes incomplete defs (AC4)."""
    mypy = _load_mypy(_scaffold_member(tmp_path))
    assert mypy is not None
    override = _tests_override(mypy)
    assert override is not None
    assert override.get("disallow_incomplete_defs") is False


def test_rendered_templates_keep_strict_block(tmp_path: Path) -> None:
    """Rendered templates keep their src strict block intact (AC4)."""
    for pyproject in (_scaffold_standalone(tmp_path), _scaffold_member(tmp_path)):
        mypy = _load_mypy(pyproject)
        assert mypy is not None
        assert mypy.get("strict") is True
        assert mypy.get("disallow_incomplete_defs") is True
        assert mypy.get("check_untyped_defs") is True
