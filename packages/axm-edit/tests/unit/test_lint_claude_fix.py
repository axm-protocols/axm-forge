"""Unit tests for claude subprocess auto-fix of remaining ruff errors."""

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


def _make_errors(file: str, codes: list[str], *, line: int = 1) -> list[str]:
    """Build ruff-style error strings."""
    return [f"{file}:{line}:{1}: {code} Some error description" for code in codes]


def _claude_completed(stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


class TestClaudeFixAppliesCorrection:
    """Mock claude returning JSON edits -> file content updated."""

    def test_line_level_fix_applied(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        # Claude returns JSON old/new edits
        fixed_output = json.dumps([{"old": "except:", "new": "except Exception:"}])

        mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            return_value=_claude_completed(fixed_output),
        )

        errors = _make_errors("app.py", ["E722"], line=3)
        claude_fix(project, errors)

        content = (project / "app.py").read_text()
        assert "except Exception:" in content, "Claude fix should be applied"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestClaudeReturnsGarbage:
    """Non-parseable output -> original code unchanged, errors returned."""

    def test_garbage_output(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        original_content = (project / "app.py").read_text()

        mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="<garbage>\x00\xff not valid python",
                stderr="error occurred",
            ),
        )

        errors = _make_errors("app.py", ["E722"])
        remaining = claude_fix(project, errors)

        assert (project / "app.py").read_text() == original_content
        assert remaining, "Should return original errors when claude output is garbage"


class TestClaudeNotInPath:
    """`FileNotFoundError` on subprocess -> skip claude fix, return ruff errors."""

    def test_file_not_found(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        original_content = (project / "app.py").read_text()

        mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            side_effect=FileNotFoundError("claude: command not found"),
        )

        errors = _make_errors("app.py", ["E722"])
        remaining = claude_fix(project, errors)

        assert (project / "app.py").read_text() == original_content
        assert remaining == errors, "Should return original errors"


class TestClaudeSubprocessTimeout:
    """Claude subprocess hangs -> kill after timeout, return original errors."""

    def test_timeout_handled(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        original_content = (project / "app.py").read_text()

        mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=60),
        )

        errors = _make_errors("app.py", ["E722"])
        remaining = claude_fix(project, errors)

        assert (project / "app.py").read_text() == original_content
        assert remaining, "Should return original errors on timeout"


class TestClaudeUnparseableOutput:
    """Claude returns non-JSON text -> no changes, errors returned."""

    def test_unparseable_format(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        original_content = (project / "app.py").read_text()

        mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            return_value=_claude_completed(
                "Here is the fix:\nexcept Exception:\n    pass\n"
            ),
        )

        errors = _make_errors("app.py", ["E722"])
        remaining = claude_fix(project, errors)

        assert (project / "app.py").read_text() == original_content
        assert remaining == errors, (
            "Should return original errors when output is not valid JSON"
        )
