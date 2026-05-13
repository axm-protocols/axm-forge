"""Integration tests extracted from test_hooks.py."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from axm_ast.hooks.trace_source import TraceSourceHook, _resolve_scope


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


class TestTraceSourceHookExecuteIntegration:
    """Integration tests for the full execute flow."""

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
        mock_trace.return_value = ([mock_step], False)

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


class TestImpactHookExecuteIntegration:
    """Tests for ImpactHook — single and multi-symbol analysis."""

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
            tmp_path, "Foo", project_root=tmp_path.parent, exclude_tests=False
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


class TestDocImpactHookExecuteIntegration:
    """Tests for DocImpactHook — single and multi-symbol doc impact analysis."""

    @patch("axm_ast.core.doc_impact.analyze_doc_impact")
    def test_doc_impact_hook_execute(
        self,
        mock_doc_impact: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Context with path + symbols → HookResult success with doc_refs."""
        from axm_ast.hooks.impact import DocImpactHook

        mock_doc_impact.return_value = {
            "doc_refs": {
                "Foo": [{"file": "README.md", "line": 10}],
            },
            "undocumented": [],
            "stale_signatures": [],
        }

        hook = DocImpactHook()
        result = hook.execute({}, symbol="Foo", path=str(tmp_path))

        assert result.success
        mock_doc_impact.assert_called_once_with(tmp_path, ["Foo"])
        assert result.metadata["doc_refs"] == {
            "Foo": [{"file": "README.md", "line": 10}],
        }

    @patch("axm_ast.core.doc_impact.analyze_doc_impact")
    def test_doc_impact_hook_multi_symbols(
        self,
        mock_doc_impact: MagicMock,
        tmp_path: Path,
    ) -> None:
        """symbols="Foo\\nBar" → Results for both symbols."""
        from axm_ast.hooks.impact import DocImpactHook

        mock_doc_impact.return_value = {
            "doc_refs": {
                "Foo": [{"file": "README.md", "line": 5}],
                "Bar": [{"file": "docs/api.md", "line": 12}],
            },
            "undocumented": [],
            "stale_signatures": [],
        }

        hook = DocImpactHook()
        result = hook.execute({}, symbol="Foo\nBar", path=str(tmp_path))

        assert result.success
        mock_doc_impact.assert_called_once_with(tmp_path, ["Foo", "Bar"])
        assert "Foo" in result.metadata["doc_refs"]
        assert "Bar" in result.metadata["doc_refs"]
