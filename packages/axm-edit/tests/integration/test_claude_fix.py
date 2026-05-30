"""Integration tests for claude subprocess auto-fix of remaining ruff errors."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from axm_edit.services.lint import claude_fix

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Minimal project with a Python file containing an unfixable ruff error."""
    src = tmp_path / "app.py"
    src.write_text("try:\n    x = 1\nexcept:\n    pass\n")
    return tmp_path


@pytest.fixture
def multi_file_project(tmp_path: Path) -> Path:
    """Project with unfixable errors across two files."""
    (tmp_path / "file_a.py").write_text(
        "try:\n    a = 1\nexcept:\n    pass\n"
        "try:\n    b = 2\nexcept:\n    pass\n"
        "try:\n    c = 3\nexcept:\n    pass\n"
    )
    (tmp_path / "file_b.py").write_text("try:\n    d = 4\nexcept:\n    pass\n")
    return tmp_path


def _make_errors(file: str, codes: list[str], *, line: int = 1) -> list[str]:
    """Build ruff-style error strings."""
    return [f"{file}:{line}:{1}: {code} Some error description" for code in codes]


def _claude_completed(stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def _is_claude_call(call_obj: Any) -> bool:
    """Check if a mock call is a claude subprocess invocation."""
    args = call_obj.args[0] if call_obj.args else []
    return isinstance(args, list) and len(args) > 0 and args[0] == "claude"


class TestClaudeFixCalledOnRemainingErrors:
    """File with unfixable ruff error -> `claude -p` subprocess spawned."""

    def test_subprocess_spawned(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        mock_run = mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            return_value=_claude_completed(),
        )

        errors = _make_errors("app.py", ["E722"])
        claude_fix(project, errors)

        claude_calls = [c for c in mock_run.call_args_list if _is_claude_call(c)]
        assert len(claude_calls) >= 1, "Expected claude subprocess to be spawned"


class TestClaudeFixPromptContainsErrors:
    """Mock subprocess -> prompt includes error codes + snippets."""

    def test_prompt_includes_error_code(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        mock_run = mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            return_value=_claude_completed(),
        )

        errors = _make_errors("app.py", ["E722"])
        claude_fix(project, errors)

        claude_calls = [c for c in mock_run.call_args_list if _is_claude_call(c)]
        assert claude_calls
        cmd_args = claude_calls[0].args[0]
        # The prompt is the 3rd arg (after "claude", "-p")
        prompt = cmd_args[2]
        assert "E722" in prompt, "Prompt must include the error code"

    def test_prompt_contains_snippets_not_full_file(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        # Write a 50-line file — error on line 3
        # 50 < 300 threshold -> full file is now sent (AXM-969)
        lines = [f"line_{i} = {i}" for i in range(50)]
        lines[2] = "try:\n    x = 1\nexcept:\n    pass"
        (project / "app.py").write_text("\n".join(lines) + "\n")

        mock_run = mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            return_value=_claude_completed(),
        )

        errors = _make_errors("app.py", ["E722"], line=3)
        claude_fix(project, errors)

        claude_calls = [c for c in mock_run.call_args_list if _is_claude_call(c)]
        assert claude_calls
        prompt = claude_calls[0].args[0][2]
        # Small file (50 lines < 300): full file content is sent
        assert "line_40" in prompt, (
            "Small file should use full-file prompt (< 300 threshold)"
        )
        # Should still contain nearby lines
        assert "line_2" in prompt or "line_1" in prompt, (
            "Prompt should contain nearby context"
        )


class TestClaudeFixCliFlags:
    """AC3: claude -p called with --system-prompt, --allowedTools, --model."""

    def test_cli_flags_present(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        mock_run = mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            return_value=_claude_completed(),
        )

        errors = _make_errors("app.py", ["E722"])
        claude_fix(project, errors)

        claude_calls = [c for c in mock_run.call_args_list if _is_claude_call(c)]
        assert claude_calls
        cmd_args = claude_calls[0].args[0]

        assert "--system-prompt" in cmd_args
        assert "--allowedTools" in cmd_args
        assert "--model" in cmd_args
        assert "claude-opus-4-6" in cmd_args
        assert "--output-format" in cmd_args
        assert "text" in cmd_args

        # --allowedTools should be followed by empty string
        idx = cmd_args.index("--allowedTools")
        assert cmd_args[idx + 1] == ""


class TestClaudeFixMaxOneRetry:
    """Error persists after fix -> returns lint_errors, no second claude call."""

    def test_max_one_retry(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        # Claude returns a JSON fix, but ruff re-check still finds errors
        fixed_output = json.dumps([{"old": "except:", "new": "except Exception:"}])

        def side_effect(
            cmd: list[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            if cmd[0] == "claude":
                return _claude_completed(fixed_output)
            # ruff check re-verification still finds errors
            if cmd[0] == "ruff":
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=1,
                    stdout="app.py:3:1: E722 Still broken\n",
                    stderr="",
                )
            return _claude_completed()

        mock_run = mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            side_effect=side_effect,
        )

        errors = _make_errors("app.py", ["E722"], line=3)
        remaining = claude_fix(project, errors)

        assert remaining, "Should return remaining errors when ruff re-check fails"

        # Claude should only be called once per file (no retry loop)
        claude_calls = [c for c in mock_run.call_args_list if _is_claude_call(c)]
        assert len(claude_calls) == 1, "Claude must be called at most once per file"


class TestClaudeFixGroupsByFile:
    """3 errors in file A, 1 in file B -> 2 subprocess calls."""

    def test_groups_by_file(
        self,
        multi_file_project: Path,
        mocker: Any,
    ) -> None:
        mock_run = mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            return_value=_claude_completed(),
        )

        errors = [
            *_make_errors("file_a.py", ["E722", "E722", "E722"]),
            *_make_errors("file_b.py", ["E722"]),
        ]
        claude_fix(multi_file_project, errors)

        claude_calls = [c for c in mock_run.call_args_list if _is_claude_call(c)]
        assert len(claude_calls) == 2, "Should spawn one claude call per file"


class TestClaudeFixRuffRecheck:
    """AC6: After applying fix, ruff check runs to verify."""

    def test_ruff_recheck_after_fix(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        fixed_output = json.dumps([{"old": "except:", "new": "except Exception:"}])

        call_order: list[str] = []

        def side_effect(
            cmd: list[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            if cmd[0] == "claude":
                call_order.append("claude")
                return _claude_completed(fixed_output)
            if cmd[0] == "ruff":
                call_order.append("ruff")
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout="",
                    stderr="",
                )
            return _claude_completed()

        mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            side_effect=side_effect,
        )

        errors = _make_errors("app.py", ["E722"], line=3)
        remaining = claude_fix(project, errors)

        assert "claude" in call_order, "Claude should be called"
        assert "ruff" in call_order, "Ruff re-check should run after claude fix"
        assert call_order.index("claude") < call_order.index("ruff"), (
            "Ruff re-check must run after claude fix"
        )
        assert remaining == [], "No remaining errors when ruff re-check passes"


class TestEmptyRemainingErrors:
    """ruff --fix solved everything -> no claude subprocess spawned."""

    def test_no_subprocess_on_empty(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        mock_run = mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            return_value=_claude_completed(),
        )

        remaining = claude_fix(project, [])

        assert remaining == []
        mock_run.assert_not_called()
