"""Tests for axm_edit.tools.run_command — RunCommandTool."""

from __future__ import annotations

from pathlib import Path

from axm_edit.tools.run_command import RunCommandTool


class TestRunCommandTool:
    """Tests for the RunCommandTool AXMTool wrapper."""

    def test_name(self) -> None:
        tool = RunCommandTool()
        assert tool.name == "run_command"

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

    def test_blocked_command_sudo(self, tmp_project: Path) -> None:
        """sudo commands are blocked."""
        result = RunCommandTool().execute(
            path=str(tmp_project), command="sudo rm -rf /"
        )
        assert result.success is False
        assert "blocked" in (result.error or "").lower()

    def test_blocked_command_rm_rf_root(self, tmp_project: Path) -> None:
        """rm -rf / is blocked."""
        result = RunCommandTool().execute(path=str(tmp_project), command="rm -rf /")
        assert result.success is False
        assert "blocked" in (result.error or "").lower()

    def test_cwd_outside_root(self, tmp_project: Path) -> None:
        """cwd outside root is sandboxed."""
        result = RunCommandTool().execute(
            path=str(tmp_project),
            command="echo test",
            cwd="../../",
        )
        assert result.success is False
        assert "escapes" in (result.error or "").lower()

    def test_empty_command(self, tmp_project: Path) -> None:
        """Empty command returns error."""
        result = RunCommandTool().execute(path=str(tmp_project), command="")
        assert result.success is False
        assert "command" in (result.error or "").lower()

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

    def test_bad_root(self) -> None:
        """Non-existent root directory returns error."""
        result = RunCommandTool().execute(path="/nonexistent/root", command="echo test")
        assert result.success is False
        assert "not a directory" in (result.error or "").lower()

    def test_command_not_found(self, tmp_project: Path) -> None:
        """Non-existent command returns error."""
        result = RunCommandTool().execute(
            path=str(tmp_project),
            command="nonexistent_command_xyz_12345",
        )
        assert result.success is False
        assert "not found" in (result.error or "").lower()

    def test_cwd_not_a_directory(self, tmp_project: Path) -> None:
        """cwd pointing to a file returns error."""
        result = RunCommandTool().execute(
            path=str(tmp_project),
            command="echo test",
            cwd="src/foo.py",
        )
        assert result.success is False
        assert "not a directory" in (result.error or "").lower()
