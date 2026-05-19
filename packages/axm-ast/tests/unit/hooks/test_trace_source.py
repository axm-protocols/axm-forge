"""Unit tests for axm_ast.hooks.trace_source — input validation only (no I/O)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from axm_ast.hooks.trace_source import TraceSourceHook, parse_entry


class TestTraceSourceHookValidation:
    """Input validation tests for TraceSourceHook.execute (no I/O)."""

    @pytest.fixture()
    def hook(self) -> TraceSourceHook:
        return TraceSourceHook()

    def test_missing_entry_param(self, hook: TraceSourceHook) -> None:
        result = hook.execute(context={"working_dir": "."})
        assert not result.success
        assert "entry" in (result.error or "")

    def test_bad_working_dir(self, hook: TraceSourceHook) -> None:
        result = hook.execute(
            context={"working_dir": "/nonexistent/path"},
            entry="foo",
        )
        assert not result.success


# ── parse_entry tests (merged from tests/unit/test_hooks.py) ────────────────


class TestParseEntry:
    """Test the SWE-bench / pytest / simple entry format parser."""

    def test_swe_bench_format(self) -> None:
        """SWE-bench: 'test_name (module.path.ClassName)'."""
        name, test_dir = parse_entry(
            "test_memoryview_content (httpwrappers.tests.HttpResponseTests)",
        )
        assert name == "test_memoryview_content"
        assert test_dir == "httpwrappers"

    def test_swe_bench_format_nested_module(self) -> None:
        """SWE-bench with deeper module path."""
        name, test_dir = parse_entry(
            "test_foo (admin.views.tests.AdminViewTests)",
        )
        assert name == "test_foo"
        assert test_dir == "admin"

    def test_swe_bench_format_single_module(self) -> None:
        """SWE-bench with single-level module (no dots in class path)."""
        name, test_dir = parse_entry(
            "test_bar (mymodule.MyTestCase)",
        )
        assert name == "test_bar"
        assert test_dir == "mymodule"

    def test_pytest_format_with_class(self) -> None:
        """Pytest: 'tests/path/file.py::ClassName::method'."""
        name, test_dir = parse_entry(
            "tests/forms_tests/tests/test_forms.py::FormsTestCase::test_foo",
        )
        assert name == "test_foo"
        assert test_dir == "tests/forms_tests/tests"

    def test_pytest_format_class_only(self) -> None:
        """Pytest with only class: 'tests/path/file.py::ClassName'."""
        name, test_dir = parse_entry(
            "tests/httpwrappers/tests.py::HttpResponseTests",
        )
        assert name == "HttpResponseTests"
        assert test_dir == "tests/httpwrappers"

    def test_simple_symbol(self) -> None:
        """Plain symbol name — no parsing needed."""
        name, test_dir = parse_entry("HttpResponse")
        assert name == "HttpResponse"
        assert test_dir is None

    def test_simple_dotted_symbol(self) -> None:
        """Dotted symbol (Class.method) — no directory extraction."""
        name, test_dir = parse_entry("HttpResponse.__init__")
        assert name == "HttpResponse.__init__"
        assert test_dir is None


# ── TraceSourceHook.execute tests (merged from tests/unit/test_hooks.py) ─────


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
