"""Unit tests for axm_audit.core.fix.findings adapter — AC1, AC2, AC3, AC4."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from axm_audit.core.fix.findings import (
    _check_by_rule,
    _load_project_scripts,
    collect_unfixable,
    get_pkg_prefixes,
)


def test_check_by_rule_returns_findings_list(
    make_pkg: Callable[..., Path],
) -> None:
    """AC1: returns list[dict] for a mis-tiered test; each dict has path + level."""
    pkg = make_pkg(
        files={
            "tests/integration/test_x.py": (
                "def test_x() -> None:\n    assert 1 == 1\n"
            ),
        }
    )
    result = _check_by_rule(pkg, "TEST_QUALITY_PYRAMID_LEVEL")
    assert isinstance(result, list)
    for f in result:
        assert isinstance(f, dict)
        assert "path" in f
        assert "level" in f


def test_check_by_rule_empty_when_clean(
    make_pkg: Callable[..., Path],
) -> None:
    """AC1: returns empty list when no PYRAMID_LEVEL finding."""
    pkg = make_pkg()
    assert _check_by_rule(pkg, "TEST_QUALITY_PYRAMID_LEVEL") == []


def test_get_pkg_prefixes_reads_deptry_config(
    make_pkg: Callable[..., Path],
) -> None:
    """AC2: exposes the first-party package name (deptry-config friendly setup)."""
    pkg = make_pkg(
        pyproject_extras='[tool.deptry]\nknown_first_party = ["mypkg"]\n',
        pkg_name="mypkg",
    )
    assert get_pkg_prefixes(pkg) == {"mypkg"}


def test_get_pkg_prefixes_falls_back_to_src_scan(
    make_pkg: Callable[..., Path],
) -> None:
    """AC2: derives package name by scanning src/ when no deptry config present."""
    pkg = make_pkg(pkg_name="mypkg")
    assert get_pkg_prefixes(pkg) == {"mypkg"}


def test_load_project_scripts_reads_pyproject(
    make_pkg: Callable[..., Path],
) -> None:
    """AC3: reads [project.scripts] and returns the entry-point name set."""
    pkg = make_pkg(
        pyproject_extras='[project.scripts]\nmy-cli = "my.module:main"\n',
    )
    assert _load_project_scripts(pkg) == {"my-cli"}


def test_collect_unfixable_surfaces_no_package_symbol(
    make_pkg: Callable[..., Path],
) -> None:
    """AC4: surfaces TEST_QUALITY_NO_PACKAGE_SYMBOL (NON_DETERMINISTIC_RULES)."""
    pkg = make_pkg(
        files={
            "tests/integration/test_x.py": (
                "def test_x() -> None:\n    assert 1 == 1\n"
            ),
        }
    )
    result = collect_unfixable(pkg)
    assert any(f.get("rule_id") == "TEST_QUALITY_NO_PACKAGE_SYMBOL" for f in result)
