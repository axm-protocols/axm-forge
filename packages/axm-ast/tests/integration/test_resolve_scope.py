"""Split from ``test_hooks.py``."""

from pathlib import Path

from axm_ast.hooks.trace_source import resolve_scope


class TestResolveScope:
    """Test scoped path resolution from test_dir."""

    def test_scope_from_swe_bench(self, tmp_path: Path) -> None:
        """Scope to tests/{module} when it exists."""
        test_dir = tmp_path / "tests" / "httpwrappers"
        test_dir.mkdir(parents=True)
        result = resolve_scope(tmp_path, "httpwrappers")
        assert result == test_dir

    def test_fallback_to_repo_root(self, tmp_path: Path) -> None:
        """Fallback to repo root when scoped dir doesn't exist."""
        result = resolve_scope(tmp_path, "nonexistent_module")
        assert result == tmp_path

    def test_none_test_dir(self, tmp_path: Path) -> None:
        """None test_dir → use base_path directly."""
        result = resolve_scope(tmp_path, None)
        assert result == tmp_path

    def test_pytest_relative_path(self, tmp_path: Path) -> None:
        """Pytest format gives a relative path with tests/ prefix."""
        test_dir = tmp_path / "tests" / "forms_tests" / "tests"
        test_dir.mkdir(parents=True)
        result = resolve_scope(tmp_path, "tests/forms_tests/tests")
        assert result == test_dir
