"""Tests for axm_edit.tools.run_command — RunCommandTool."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.tools.run_command import RunCommandTool


class TestRunCommandTool:
    """Tests for the RunCommandTool AXMTool wrapper."""

    def test_echo(self, tmp_project: Path) -> None:
        """Simple echo command returns stdout."""
        result = RunCommandTool().execute(path=str(tmp_project), command="echo hello")
        assert result.success is True
        assert result.data is not None
        assert result.data["stdout"].strip() == "hello"
        assert result.data["exit_code"] == 0
        assert result.data["timed_out"] is False

    def test_exit_code(self, tmp_project: Path) -> None:
        """Non-zero exit code is captured."""
        result = RunCommandTool().execute(path=str(tmp_project), command="false")
        assert result.success is True
        assert result.data is not None
        assert result.data["exit_code"] != 0

    def test_timeout(self, tmp_project: Path) -> None:
        """Command exceeding timeout is killed."""
        result = RunCommandTool().execute(
            path=str(tmp_project), command="sleep 10", timeout=1
        )
        assert result.success is True
        assert result.data is not None
        assert result.data["timed_out"] is True
        assert result.data["exit_code"] == -1

    def test_truncation(self, tmp_project: Path) -> None:
        """Output longer than 4096 chars is truncated."""
        # Generate output >4096 chars
        result = RunCommandTool().execute(
            path=str(tmp_project),
            command="python3 -c \"print('A' * 10000)\"",
        )
        assert result.success is True
        assert result.data is not None
        assert result.data["truncated"] is True
        assert len(result.data["stdout"]) <= 4096 + len("\n[truncated]") + 1

    @pytest.mark.parametrize(
        ("command", "error_substr"),
        [
            pytest.param("sudo rm -rf /", "blocked", id="sudo"),
            pytest.param("rm -rf /", "blocked", id="rm_rf_root"),
            pytest.param("", "command", id="empty"),
            pytest.param("nonexistent_command_xyz_12345", "not found", id="not_found"),
        ],
    )
    def test_rejected_command(
        self, tmp_project: Path, command: str, error_substr: str
    ) -> None:
        """Blocked, empty, and not-found commands fail with a matching error."""
        result = RunCommandTool().execute(path=str(tmp_project), command=command)
        assert result.success is False
        assert error_substr in (result.error or "").lower()

    @pytest.mark.parametrize(
        ("cwd", "error_substr"),
        [
            pytest.param("../../", "escapes", id="outside_root"),
            pytest.param("src/foo.py", "not a directory", id="not_a_directory"),
        ],
    )
    def test_invalid_cwd(self, tmp_project: Path, cwd: str, error_substr: str) -> None:
        """cwd escaping root or pointing to a file fails with a matching error."""
        result = RunCommandTool().execute(
            path=str(tmp_project),
            command="echo test",
            cwd=cwd,
        )
        assert result.success is False
        assert error_substr in (result.error or "").lower()

    def test_missing_command(self, tmp_project: Path) -> None:
        """Missing command argument returns error."""
        result = RunCommandTool().execute(path=str(tmp_project))
        assert result.success is False
        assert "command" in (result.error or "").lower()

    def test_stderr_output(self, tmp_project: Path) -> None:
        """stderr is captured separately."""
        result = RunCommandTool().execute(
            path=str(tmp_project),
            command="python3 -c \"import sys; sys.stderr.write('warning\\n')\"",
        )
        assert result.success is True
        assert result.data is not None
        assert "warning" in result.data["stderr"]

    def test_cwd_relative(self, tmp_project: Path) -> None:
        """cwd relative to root is resolved correctly."""
        result = RunCommandTool().execute(
            path=str(tmp_project),
            command="ls",
            cwd="src",
        )
        assert result.success is True
        assert result.data is not None
        assert "foo.py" in result.data["stdout"]
