"""Tests for resolve_working_dir helper."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from axm_git.hooks._resolve import resolve_working_dir


class TestResolveWorkingDir:
    """Tests for resolve_working_dir."""

    @pytest.mark.parametrize(
        ("params", "context", "expected"),
        [
            pytest.param(
                {}, {"worktree_path": "/tmp/wt"}, Path("/tmp/wt"), id="string"
            ),
            pytest.param(
                {},
                {"worktree_path": {"worktree_path": "/tmp/wt", "branch": "x"}},
                Path("/tmp/wt"),
                id="dict",
            ),
            pytest.param(
                {"working_dir": "/other"},
                {"worktree_path": {"worktree_path": "/tmp/wt", "branch": "x"}},
                Path("/other"),
                id="params_override",
            ),
            pytest.param(
                {},
                {"working_dir": "/fallback"},
                Path("/fallback"),
                id="fallback_working_dir",
            ),
            pytest.param({}, {}, Path("."), id="default"),
        ],
    )
    def test_resolve_working_dir(
        self,
        params: dict[str, Any],
        context: dict[str, Any],
        expected: Path,
    ) -> None:
        assert resolve_working_dir(params, context) == expected

    def test_resolve_working_dir_custom_param_key(self) -> None:
        """Custom param_key reads from that key instead of working_dir."""
        params = {"path": "/custom"}
        result = resolve_working_dir(params, {}, param_key="path")
        assert result == Path("/custom")
