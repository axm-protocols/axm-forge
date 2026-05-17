from __future__ import annotations

from typing import Any, cast

import pytest

from axm_ast.core.impact import ImpactResult
from axm_ast.hooks.impact import DocImpactHook, ImpactHook, _merge_impact_reports


def test_impact_module_all_exports() -> None:
    """DocImpactHook must be listed in __all__."""
    from axm_ast.hooks.impact import __all__

    assert "DocImpactHook" in __all__


def test_import_star_exposes_doc_impact_hook() -> None:
    """'from axm_ast.hooks.impact import *' must make DocImpactHook available."""
    ns: dict[str, object] = {}
    exec("from axm_ast.hooks.impact import *", ns)  # noqa: S102
    assert "DocImpactHook" in ns


@pytest.fixture
def hook() -> ImpactHook:
    return ImpactHook()


class TestImpactHookUnit:
    """Pure unit cases (no filesystem I/O)."""

    def test_impact_hook_no_symbol(self) -> None:
        """Missing symbol param → HookResult.fail."""
        hook = ImpactHook()
        result = hook.execute({})
        assert not result.success
        assert "symbol" in (result.error or "").lower()


# ── _merge_impact_reports tests (merged from test_hooks.py) ─────────────────


class TestMergeImpactReports:
    """Tests for _merge_impact_reports helper."""

    def test_single_report(self) -> None:
        """Single report returned unchanged."""
        report: dict[str, Any] = {
            "symbol": "Foo",
            "definition": {"file": "foo.py", "line": 10},
            "callers": [{"name": "bar"}],
            "type_refs": [],
            "reexports": [],
            "affected_modules": ["mod_a"],
            "test_files": ["test_foo.py"],
            "git_coupled": [],
            "score": "MEDIUM",
        }
        result = _merge_impact_reports("Foo", cast("list[ImpactResult]", [report]))
        assert result["callers"] == [{"name": "bar"}]
        assert result["score"] == "MEDIUM"
        assert result["affected_modules"] == ["mod_a"]

    def test_multi_reports_max_score(self) -> None:
        """Max score wins across multiple reports."""
        r1: dict[str, Any] = {
            "definition": {"file": "a.py", "line": 1},
            "callers": [{"name": "x"}],
            "type_refs": [],
            "reexports": [],
            "affected_modules": ["mod_a"],
            "test_files": ["test_a.py"],
            "git_coupled": [],
            "score": "LOW",
        }
        r2: dict[str, Any] = {
            "definition": {"file": "b.py", "line": 5},
            "callers": [{"name": "y"}],
            "type_refs": [],
            "reexports": [],
            "affected_modules": ["mod_b"],
            "test_files": ["test_b.py"],
            "git_coupled": [],
            "score": "HIGH",
        }
        result = _merge_impact_reports("A\nB", cast("list[ImpactResult]", [r1, r2]))
        assert result["score"] == "HIGH"
        assert len(result["callers"]) == 2
        assert len(result["definitions"]) == 2

    def test_dedup_modules_and_tests(self) -> None:
        """affected_modules and test_files are deduplicated."""
        r1: dict[str, Any] = {
            "definition": None,
            "callers": [],
            "type_refs": [],
            "reexports": [],
            "affected_modules": ["mod_a", "mod_b"],
            "test_files": ["test_x.py"],
            "git_coupled": [],
            "score": "LOW",
        }
        r2: dict[str, Any] = {
            "definition": None,
            "callers": [],
            "type_refs": [],
            "reexports": [],
            "affected_modules": ["mod_a", "mod_c"],
            "test_files": ["test_x.py", "test_y.py"],
            "git_coupled": [],
            "score": "LOW",
        }
        result = _merge_impact_reports("A\nB", cast("list[ImpactResult]", [r1, r2]))
        assert result["affected_modules"] == ["mod_a", "mod_b", "mod_c"]
        assert result["test_files"] == ["test_x.py", "test_y.py"]


# ── ImpactHook execute tests (merged from test_hooks.py) ────────────────────


class TestImpactHookExecuteUnit:
    """Tests for ImpactHook — single and multi-symbol analysis."""

    def test_missing_symbol(self) -> None:
        """Fail when 'symbol' param is missing."""
        hook = ImpactHook()
        result = hook.execute({})
        assert not result.success
        assert result.error is not None
        assert "symbol" in result.error

    def test_invalid_path(self) -> None:
        """Fail when path doesn't exist."""
        hook = ImpactHook()
        result = hook.execute({}, symbol="Foo", path="/nonexistent/dir")
        assert not result.success
        assert result.error is not None
        assert "not a directory" in result.error


class TestDocImpactHookExecuteUnit:
    """Tests for DocImpactHook — single and multi-symbol doc impact analysis."""

    def test_missing_symbol(self) -> None:
        """Fail when 'symbol' param is missing."""
        hook = DocImpactHook()
        result = hook.execute({})
        assert not result.success
        assert result.error is not None
        assert "symbol" in result.error

    def test_invalid_path(self) -> None:
        """Fail when path doesn't exist."""
        hook = DocImpactHook()
        result = hook.execute({}, symbol="Foo", path="/nonexistent/dir")
        assert not result.success
        assert result.error is not None
        assert "not a directory" in result.error
