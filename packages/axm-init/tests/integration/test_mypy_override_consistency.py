from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

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
