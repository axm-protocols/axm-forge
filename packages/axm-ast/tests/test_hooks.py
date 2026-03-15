"""Tests for TraceSourceHook and ImpactHook."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from axm_ast.hooks.trace_source import TraceSourceHook, _parse_entry, _resolve_scope

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


# ── _resolve_scope tests ────────────────────────────────────────────


class TestResolveScope:
    """Test scoped path resolution from test_dir."""

    def test_scope_from_swe_bench(self, tmp_path: Path) -> None:
        """Scope to tests/{module} when it exists."""
        test_dir = tmp_path / "tests" / "httpwrappers"
        test_dir.mkdir(parents=True)
        result = _resolve_scope(tmp_path, "httpwrappers")
        assert result == test_dir

    def test_fallback_to_repo_root(self, tmp_path: Path) -> None:
        """Fallback to repo root when scoped dir doesn't exist."""
        result = _resolve_scope(tmp_path, "nonexistent_module")
        assert result == tmp_path

    def test_none_test_dir(self, tmp_path: Path) -> None:
        """None test_dir → use base_path directly."""
        result = _resolve_scope(tmp_path, None)
        assert result == tmp_path

    def test_pytest_relative_path(self, tmp_path: Path) -> None:
        """Pytest format gives a relative path with tests/ prefix."""
        test_dir = tmp_path / "tests" / "forms_tests" / "tests"
        test_dir.mkdir(parents=True)
        result = _resolve_scope(tmp_path, "tests/forms_tests/tests")
        assert result == test_dir


# ── TraceSourceHook.execute integration tests ───────────────────────


class TestTraceSourceHookExecute:
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
    def test_swe_bench_entry_scopes_path(
        self,
        mock_analyze: MagicMock,
        mock_trace: MagicMock,
        tmp_path: Path,
    ) -> None:
        """SWE-bench format entry scopes analyze_package to test dir."""
        # Setup: create tests/httpwrappers dir
        test_dir = tmp_path / "tests" / "httpwrappers"
        test_dir.mkdir(parents=True)

        mock_pkg = MagicMock()
        mock_analyze.return_value = mock_pkg
        mock_step = MagicMock()
        mock_step.model_dump.return_value = {"name": "test_foo", "depth": 0}
        mock_trace.return_value = [mock_step]

        hook = TraceSourceHook()
        result = hook.execute(
            {},
            entry="test_memoryview_content (httpwrappers.tests.HttpResponseTests)",
            path=str(tmp_path),
        )

        assert result.success
        # Verify analyze_package was called with the scoped path
        mock_analyze.assert_called_once_with(test_dir)
        # Verify trace_flow got the parsed entry name
        mock_trace.assert_called_once()
        call_args = mock_trace.call_args
        assert call_args[0][1] == "test_memoryview_content"

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
        mock_trace.return_value = []

        hook = TraceSourceHook()
        result = hook.execute({}, entry="HttpResponse", path=str(tmp_path))

        assert result.success
        mock_analyze.assert_called_once_with(tmp_path)


# ── ImpactHook tests ────────────────────────────────────────────────


class TestImpactHookExecute:
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

    @patch("axm_ast.core.impact.analyze_impact")
    def test_single_symbol(
        self,
        mock_impact: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Single symbol — passes through directly, no merge."""
        from axm_ast.hooks.impact import ImpactHook

        mock_impact.return_value = {
            "symbol": "Foo",
            "definition": {"file": "foo.py", "line": 10},
            "callers": [{"name": "bar", "file": "bar.py"}],
            "type_refs": [],
            "reexports": [],
            "affected_modules": ["mod_a"],
            "test_files": ["test_foo.py"],
            "git_coupled": [],
            "score": "MEDIUM",
        }

        hook = ImpactHook()
        result = hook.execute({}, symbol="Foo", path=str(tmp_path))

        assert result.success
        mock_impact.assert_called_once_with(
            tmp_path, "Foo", project_root=tmp_path.parent
        )
        assert result.metadata["impact"]["score"] == "MEDIUM"

    @patch("axm_ast.core.impact.analyze_impact")
    def test_multi_symbol_newline_split(
        self,
        mock_impact: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Newline-separated symbols are split and each analyzed."""
        from axm_ast.hooks.impact import ImpactHook

        mock_impact.return_value = {
            "symbol": "X",
            "definition": {"file": "x.py", "line": 1},
            "callers": [],
            "type_refs": [],
            "reexports": [],
            "affected_modules": [],
            "test_files": [],
            "git_coupled": [],
            "score": "LOW",
        }

        hook = ImpactHook()
        result = hook.execute({}, symbol="A\nB", path=str(tmp_path))

        assert result.success
        assert mock_impact.call_count == 2
        calls = [c.args for c in mock_impact.call_args_list]
        assert calls[0] == (tmp_path, "A")
        assert calls[1] == (tmp_path, "B")

    @patch("axm_ast.core.impact.analyze_impact")
    def test_multi_symbol_max_score(
        self,
        mock_impact: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Merged score takes the maximum across all symbols."""
        from axm_ast.hooks.impact import ImpactHook

        def side_effect(_path: Path, sym: str, **_kw: object) -> dict[str, Any]:
            base: dict[str, Any] = {
                "definition": None,
                "callers": [],
                "type_refs": [],
                "reexports": [],
                "affected_modules": [],
                "test_files": [],
                "git_coupled": [],
            }
            if sym == "A":
                return {**base, "symbol": "A", "score": "LOW"}
            return {**base, "symbol": "B", "score": "HIGH"}

        mock_impact.side_effect = side_effect

        hook = ImpactHook()
        result = hook.execute({}, symbol="A\nB", path=str(tmp_path))

        assert result.success
        assert result.metadata["impact"]["score"] == "HIGH"

    @patch("axm_ast.core.impact.analyze_impact")
    def test_multi_symbol_dedup_modules(
        self,
        mock_impact: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Affected modules and test files are deduplicated."""
        from axm_ast.hooks.impact import ImpactHook

        base: dict[str, Any] = {
            "definition": None,
            "callers": [],
            "type_refs": [],
            "reexports": [],
            "git_coupled": [],
            "score": "LOW",
        }
        mock_impact.return_value = {
            **base,
            "symbol": "X",
            "affected_modules": ["mod_a", "mod_b"],
            "test_files": ["test_x.py"],
        }

        hook = ImpactHook()
        result = hook.execute({}, symbol="A\nB", path=str(tmp_path))

        assert result.success
        impact = result.metadata["impact"]
        # Both returns identical modules — should be deduplicated
        assert impact["affected_modules"] == ["mod_a", "mod_b"]
        assert impact["test_files"] == ["test_x.py"]

    @patch("axm_ast.core.impact.analyze_impact")
    def test_whitespace_handling(
        self,
        mock_impact: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Empty lines and trailing whitespace are ignored."""
        from axm_ast.hooks.impact import ImpactHook

        mock_impact.return_value = {
            "symbol": "X",
            "definition": None,
            "callers": [],
            "type_refs": [],
            "reexports": [],
            "affected_modules": [],
            "test_files": [],
            "git_coupled": [],
            "score": "LOW",
        }

        hook = ImpactHook()
        result = hook.execute({}, symbol="A\n  \nB\n", path=str(tmp_path))

        assert result.success
        # Only A and B should be analyzed, not empty strings
        assert mock_impact.call_count == 2
