"""Integration tests: ast_cache_stats observes the real get_package singleton."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _build_pkg(root: Path) -> Path:
    pkg = root / "statspkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Stats demo."""\n')
    (pkg / "core.py").write_text("def f() -> int:\n    return 1\n")
    return pkg


def test_entry_point_resolves_to_tool_class() -> None:
    """The axm.tools entry point ast_cache_stats loads CacheStatsTool."""
    from importlib.metadata import entry_points

    from axm_ast.tools.cache_stats import CacheStatsTool

    eps = entry_points(group="axm.tools")
    ep = next(ep for ep in eps if ep.name == "ast_cache_stats")
    assert ep.load() is CacheStatsTool


def test_parse_then_hit_is_counted(tmp_path: Path) -> None:
    """One miss (parse) then one hit give a single entry and a 50% ratio."""
    from axm_ast.core.cache import clear_cache, get_package
    from axm_ast.tools.cache_stats import CacheStatsTool

    pkg = _build_pkg(tmp_path)
    clear_cache()
    get_package(pkg)
    get_package(pkg)

    result = CacheStatsTool().execute()

    assert result.success is True
    data = result.data
    assert (data["entries"], data["hits"], data["misses"]) == (1, 1, 1)
    assert data["hit_ratio"] == 0.5
    assert data["weight_bytes"] > 0
    assert data["parse_cache"]["entries"] >= 2
    assert result.text is not None
    assert "lookups: 2 · hits 1 · misses 1 · ratio 50.0%" in result.text


def test_runs_under_a_session_read_contract(tmp_path: Path) -> None:
    """In shared mode (a bound read contract) the path-less tool still answers."""
    from axm.tools.dependency_reads import dependency_read_context
    from axm.tools.write_scope import WriteContract

    from axm_ast.tools.cache_stats import CacheStatsTool

    contract = WriteContract.from_mapping({"execution_root": str(tmp_path)})
    with dependency_read_context(contract):
        result = CacheStatsTool().execute()

    assert result.success is True, result.error
    assert "entries" in result.data
