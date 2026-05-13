"""Tests for TraceSourceHook, ImpactHook, and merge helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

from axm_ast.core.impact import ImpactResult
from axm_ast.hooks.trace_source import TraceSourceHook, _parse_entry

# ── _parse_entry tests ──────────────────────────────────────────────


class TestParseEntry:
    """Test the SWE-bench / pytest / simple entry format parser."""

    def test_swe_bench_format(self) -> None:
        """SWE-bench: 'test_name (module.path.ClassName)'."""
        name, test_dir = _parse_entry(
            "test_memoryview_content (httpwrappers.tests.HttpResponseTests)",
        )
        assert name == "test_memoryview_content"
        assert test_dir == "httpwrappers"

    def test_swe_bench_format_nested_module(self) -> None:
        """SWE-bench with deeper module path."""
        name, test_dir = _parse_entry(
            "test_foo (admin.views.tests.AdminViewTests)",
        )
        assert name == "test_foo"
        assert test_dir == "admin"

    def test_swe_bench_format_single_module(self) -> None:
        """SWE-bench with single-level module (no dots in class path)."""
        name, test_dir = _parse_entry(
            "test_bar (mymodule.MyTestCase)",
        )
        assert name == "test_bar"
        assert test_dir == "mymodule"

    def test_pytest_format_with_class(self) -> None:
        """Pytest: 'tests/path/file.py::ClassName::method'."""
        name, test_dir = _parse_entry(
            "tests/forms_tests/tests/test_forms.py::FormsTestCase::test_foo",
        )
        assert name == "test_foo"
        assert test_dir == "tests/forms_tests/tests"

    def test_pytest_format_class_only(self) -> None:
        """Pytest with only class: 'tests/path/file.py::ClassName'."""
        name, test_dir = _parse_entry(
            "tests/httpwrappers/tests.py::HttpResponseTests",
        )
        assert name == "HttpResponseTests"
        assert test_dir == "tests/httpwrappers"

    def test_simple_symbol(self) -> None:
        """Plain symbol name — no parsing needed."""
        name, test_dir = _parse_entry("HttpResponse")
        assert name == "HttpResponse"
        assert test_dir is None

    def test_simple_dotted_symbol(self) -> None:
        """Dotted symbol (Class.method) — no directory extraction."""
        name, test_dir = _parse_entry("HttpResponse.__init__")
        assert name == "HttpResponse.__init__"
        assert test_dir is None


# ── TraceSourceHook.execute integration tests ───────────────────────


class TestTraceSourceHookExecuteUnit:
    """Integration tests for the full execute flow."""

    def test_missing_entry(self) -> None:
        """Fail when 'entry' param is missing."""
        hook = TraceSourceHook()
        result = hook.execute({})
        assert not result.success
        assert result.error is not None
        assert "entry" in result.error

    def test_invalid_working_dir(self) -> None:
        """Fail when path doesn't exist."""
        hook = TraceSourceHook()
        result = hook.execute({}, entry="foo", path="/nonexistent/dir")
        assert not result.success
        assert result.error is not None
        assert "not a directory" in result.error

    @patch("axm_ast.hooks.trace_source.trace_flow")
    @patch("axm_ast.hooks.trace_source.analyze_package")
    def test_simple_symbol_uses_path_directly(
        self,
        mock_analyze: MagicMock,
        mock_trace: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Simple symbol entry uses path param directly."""
        mock_analyze.return_value = MagicMock()
        mock_trace.return_value = ([], False)

        hook = TraceSourceHook()
        result = hook.execute({}, entry="HttpResponse", path=str(tmp_path))

        assert result.success
        mock_analyze.assert_called_once_with(tmp_path)


# ── _merge_impact_reports tests ─────────────────────────────────────


class TestMergeImpactReports:
    """Tests for _merge_impact_reports helper."""

    def test_single_report(self) -> None:
        """Single report returned unchanged."""
        from axm_ast.hooks.impact import _merge_impact_reports

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
        from axm_ast.hooks.impact import _merge_impact_reports

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
        from axm_ast.hooks.impact import _merge_impact_reports

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


# ── ImpactHook tests ────────────────────────────────────────────────


class TestImpactHookExecuteUnit:
    """Tests for ImpactHook — single and multi-symbol analysis."""

    def test_missing_symbol(self) -> None:
        """Fail when 'symbol' param is missing."""
        from axm_ast.hooks.impact import ImpactHook

        hook = ImpactHook()
        result = hook.execute({})
        assert not result.success
        assert result.error is not None
        assert "symbol" in result.error

    def test_invalid_path(self) -> None:
        """Fail when path doesn't exist."""
        from axm_ast.hooks.impact import ImpactHook

        hook = ImpactHook()
        result = hook.execute({}, symbol="Foo", path="/nonexistent/dir")
        assert not result.success
        assert result.error is not None
        assert "not a directory" in result.error


# ── DocImpactHook tests ─────────────────────────────────────────────


class TestDocImpactHookExecuteUnit:
    """Tests for DocImpactHook — single and multi-symbol doc impact analysis."""

    def test_missing_symbol(self) -> None:
        """Fail when 'symbol' param is missing."""
        from axm_ast.hooks.impact import DocImpactHook

        hook = DocImpactHook()
        result = hook.execute({})
        assert not result.success
        assert result.error is not None
        assert "symbol" in result.error

    def test_invalid_path(self) -> None:
        """Fail when path doesn't exist."""
        from axm_ast.hooks.impact import DocImpactHook

        hook = DocImpactHook()
        result = hook.execute({}, symbol="Foo", path="/nonexistent/dir")
        assert not result.success
        assert result.error is not None
        assert "not a directory" in result.error
