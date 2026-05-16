"""Split from ``test_makefile_tool_command_detection.py``."""

from pathlib import Path

import pytest


class TestGetToolCommand:
    """Tests for tool command resolution."""

    @pytest.mark.parametrize(
        ("makefile_body", "expected"),
        [
            pytest.param(
                "lint:\n\tuv run ruff check .\n",
                ["make", "lint"],
                id="make_target_available",
            ),
            pytest.param(
                None,
                ["uv", "run", "ruff", "check", "."],
                id="no_makefile",
            ),
            pytest.param(
                "build:\n\tpython -m build\n",
                ["uv", "run", "ruff", "check", "."],
                id="target_missing",
            ),
        ],
    )
    def test_get_tool_command(
        self, tmp_path: Path, makefile_body: str | None, expected: list[str]
    ) -> None:
        """get_tool_command prefers make target, otherwise returns fallback."""
        from axm_init.adapters.makefile import get_tool_command

        if makefile_body is not None:
            (tmp_path / "Makefile").write_text(makefile_body)
        cmd = get_tool_command(
            project_path=tmp_path,
            makefile_target="lint",
            fallback_cmd=["uv", "run", "ruff", "check", "."],
        )
        assert cmd == expected
