from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from axm_ast.hooks.impact import DocImpactHook, ImpactHook


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


# ── Multi-symbol merge tests via the public ImpactHook.execute seam ─────────


class TestImpactHookMultiSymbolMerge:
    """Drive the multi-symbol merge path through ImpactHook.execute.

    The hook splits ``symbol`` on newlines and merges per-symbol
    ``analyze_impact`` results (max score, concat callers, dedup
    modules/tests). These tests assert on the merged metadata shape
    exposed via ``HookResult.metadata['impact']``.
    """

    @patch("axm_ast.core.impact.analyze_impact")
    def test_single_symbol_passthrough(
        self,
        mock_impact: Any,
        tmp_path: Path,
    ) -> None:
        """Single symbol bypasses merge — fields propagate unchanged."""
        mock_impact.return_value = {
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

        result = ImpactHook().execute({}, symbol="Foo", path=str(tmp_path))

        assert result.success
        impact = result.metadata["impact"]
        assert impact["callers"] == [{"name": "bar"}]
        assert impact["score"] == "MEDIUM"
        assert impact["affected_modules"] == ["mod_a"]

    @patch("axm_ast.core.impact.analyze_impact")
    def test_multi_reports_max_score(
        self,
        mock_impact: Any,
        tmp_path: Path,
    ) -> None:
        """Max score wins across multiple symbols; definitions accumulate."""

        def side_effect(_path: Path, sym: str, **_kw: object) -> dict[str, Any]:
            base: dict[str, Any] = {
                "type_refs": [],
                "reexports": [],
                "test_files": [f"test_{sym.lower()}.py"],
                "git_coupled": [],
            }
            if sym == "A":
                return {
                    **base,
                    "symbol": "A",
                    "definition": {"file": "a.py", "line": 1},
                    "callers": [{"name": "x"}],
                    "affected_modules": ["mod_a"],
                    "score": "LOW",
                }
            return {
                **base,
                "symbol": "B",
                "definition": {"file": "b.py", "line": 5},
                "callers": [{"name": "y"}],
                "affected_modules": ["mod_b"],
                "score": "HIGH",
            }

        mock_impact.side_effect = side_effect

        result = ImpactHook().execute({}, symbol="A\nB", path=str(tmp_path))

        assert result.success
        impact = result.metadata["impact"]
        assert impact["score"] == "HIGH"
        assert len(impact["callers"]) == 2
        assert len(impact["definitions"]) == 2

    @patch("axm_ast.core.impact.analyze_impact")
    def test_dedup_modules_and_tests(
        self,
        mock_impact: Any,
        tmp_path: Path,
    ) -> None:
        """affected_modules and test_files are deduplicated across reports."""

        def side_effect(_path: Path, sym: str, **_kw: object) -> dict[str, Any]:
            base: dict[str, Any] = {
                "symbol": sym,
                "definition": None,
                "callers": [],
                "type_refs": [],
                "reexports": [],
                "git_coupled": [],
                "score": "LOW",
            }
            if sym == "A":
                return {
                    **base,
                    "affected_modules": ["mod_a", "mod_b"],
                    "test_files": ["test_x.py"],
                }
            return {
                **base,
                "affected_modules": ["mod_a", "mod_c"],
                "test_files": ["test_x.py", "test_y.py"],
            }

        mock_impact.side_effect = side_effect

        result = ImpactHook().execute({}, symbol="A\nB", path=str(tmp_path))

        assert result.success
        impact = result.metadata["impact"]
        assert impact["affected_modules"] == ["mod_a", "mod_b", "mod_c"]
        assert impact["test_files"] == ["test_x.py", "test_y.py"]


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
