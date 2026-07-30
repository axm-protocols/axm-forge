"""Split from ``test_hooks.py``."""

from pathlib import Path

import pytest

from axm_ast.hooks.trace_source import resolve_scope


class TestResolveScope:
    """Test scoped path resolution from test_dir."""

    @pytest.mark.parametrize(
        ("dir_to_create", "test_dir_arg", "expected_rel"),
        [
            pytest.param(
                "tests/httpwrappers",
                "httpwrappers",
                "tests/httpwrappers",
                id="scope_from_swe_bench",
            ),
            pytest.param(
                None,
                "nonexistent_module",
                "",
                id="fallback_to_repo_root",
            ),
            pytest.param(
                None,
                None,
                "",
                id="none_test_dir",
            ),
            pytest.param(
                "tests/forms_tests/tests",
                "tests/forms_tests/tests",
                "tests/forms_tests/tests",
                id="pytest_relative_path",
            ),
        ],
    )
    def test_resolves_scope(
        self,
        tmp_path: Path,
        dir_to_create: str | None,
        test_dir_arg: str | None,
        expected_rel: str,
    ) -> None:
        """resolve_scope routes to tests/{module} when present, else base_path."""
        if dir_to_create is not None:
            (tmp_path / dir_to_create).mkdir(parents=True)
        result = resolve_scope(tmp_path, test_dir_arg)
        expected = tmp_path / expected_rel if expected_rel else tmp_path
        assert result == expected
