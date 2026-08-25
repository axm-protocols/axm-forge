"""Tests for axm_edit.tools.run_command — RunCommandTool."""

from __future__ import annotations

from axm_edit.tools.run_command import RunCommandTool, render_text


class TestRunCommandTool:
    """Tests for the RunCommandTool AXMTool wrapper."""

    def test_name(self) -> None:
        tool = RunCommandTool()
        assert tool.name == "run_command"

    def test_bad_root(self) -> None:
        """Non-existent root directory returns error."""
        result = RunCommandTool().execute(path="/nonexistent/root", command="echo test")
        assert result.success is False
        assert "not a directory" in (result.error or "").lower()


class TestRenderText:
    """Tests for the ``render_text`` compact rendering helper."""

    def test_exit_zero_carries_stdout_verbatim(self) -> None:
        text = render_text(
            stdout="hello\nworld\n",
            stderr="",
            exit_code=0,
            timed_out=False,
            truncated=False,
        )
        assert text.startswith("run_command | exit 0\n")
        # Raw, not JSON-escaped: a real newline, not a literal backslash-n.
        assert "hello\nworld" in text
        assert "\\n" not in text

    def test_failure_marks_exit_and_keeps_stderr(self) -> None:
        text = render_text(
            stdout="",
            stderr="boom: not found",
            exit_code=2,
            timed_out=False,
            truncated=False,
        )
        assert "exit 2 ✗" in text
        assert "stderr:\nboom: not found" in text

    def test_timeout_and_truncated_flags_surface(self) -> None:
        text = render_text(
            stdout="partial",
            stderr="",
            exit_code=-1,
            timed_out=True,
            truncated=True,
        )
        assert "exit -1 ✗" in text
        assert "timeout" in text
        assert "truncated" in text

    def test_no_output_is_explicit(self) -> None:
        text = render_text(
            stdout="",
            stderr="",
            exit_code=0,
            timed_out=False,
            truncated=False,
        )
        assert text == "run_command | exit 0\n(no output)"
