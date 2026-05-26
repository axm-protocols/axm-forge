"""Tests for graceful degradation when ruff/claude are unavailable."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from axm_edit.services.lint import claude_fix
from axm_edit.tools.batch_edit import BatchEditTool

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tool() -> BatchEditTool:
    return BatchEditTool()


@pytest.fixture
def py_project(tmp_path: Path) -> Path:
    """Minimal git project with a Python file."""
    src = tmp_path / "hello.py"
    src.write_text("x = 1\n")
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_EMAIL": "t@t",
            "HOME": str(tmp_path),
        },
    )
    return tmp_path


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Minimal project with a Python file containing an unfixable ruff error."""
    src = tmp_path / "app.py"
    src.write_text("try:\n    x = 1\nexcept:\n    pass\n")
    return tmp_path


def _replace_op(file: str, old: str, new: str) -> dict[str, Any]:
    return {"op": "replace", "file": file, "edits": [{"old": old, "new": new}]}


def _make_errors(file: str, codes: list[str], *, line: int = 1) -> list[str]:
    return [f"{file}:{line}:{1}: {code} Some error description" for code in codes]


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestNoRuffSkipsLint:
    """AC1: If ruff is not in PATH, lint step is silently skipped."""

    def test_no_ruff_skips_lint(
        self,
        tool: BatchEditTool,
        py_project: Path,
        monkeypatch: pytest.MonkeyPatch,
        mocker: Any,
    ) -> None:
        monkeypatch.setattr("axm_edit.services.lint._has_ruff", False)
        spy = mocker.patch("subprocess.run", wraps=subprocess.run)

        result = tool.execute(
            path=str(py_project),
            operations=[_replace_op("hello.py", "x = 1", "x = 2")],
        )

        assert result.success
        # No ruff subprocess should have been called
        for call in spy.call_args_list:
            args = call.args[0] if call.args else call.kwargs.get("args", [])
            if isinstance(args, list):
                assert args[0] != "ruff", "ruff should not be called"


class TestNoClaudeSkipsAutofix:
    """AC2: If claude is not in PATH, claude auto-fix step silently skipped."""

    def test_no_claude_skips_autofix(
        self,
        project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("axm_edit.services.lint._has_claude", False)

        errors = _make_errors("app.py", ["E722"])
        warnings: list[str] = []
        remaining = claude_fix(project, errors, warnings=warnings)

        # Errors returned as-is, no claude call
        assert remaining == errors
        assert any("claude not found" in w for w in warnings)


class TestRuffCrashGraceful:
    """AC5: If ruff subprocess crashes (exit code 2), skip gracefully."""

    def test_ruff_crash_graceful(
        self,
        tool: BatchEditTool,
        py_project: Path,
        mocker: Any,
    ) -> None:
        # Mock claude_fix to pass through
        mocker.patch(
            "axm_edit.tools.batch_edit.claude_fix",
            side_effect=lambda root, errors, **kw: errors,
        )

        call_count = 0

        def ruff_crash(
            cmd: list[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            nonlocal call_count
            if isinstance(cmd, list) and "ruff" in cmd:
                call_count += 1
                if "--fix" in cmd:
                    # ruff fix crashes with internal error
                    return subprocess.CompletedProcess(
                        args=cmd,
                        returncode=0,
                        stdout="",
                        stderr="",
                    )
                # ruff check crashes with exit code 2 (internal error)
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=2,
                    stdout="",
                    stderr="internal error",
                )
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="",
                stderr="",
            )

        mocker.patch(
            "axm_edit.tools.batch_edit.subprocess.run",
            side_effect=ruff_crash,
        )

        result = tool.execute(
            path=str(py_project),
            operations=[
                _replace_op(
                    "hello.py",
                    "x = 1",
                    "try:\n    x = 1\nexcept:\n    pass",
                )
            ],
        )

        assert result.success
        assert result.data is not None
        assert "ruff crashed" in str(result.data.get("warnings", []))


class TestClaudeTimeoutGraceful:
    """AC6: If claude subprocess times out, skip gracefully with warning."""

    def test_claude_timeout_graceful(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        def side_effect(
            cmd: list[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            if isinstance(cmd, list) and cmd and cmd[0] == "claude":
                raise subprocess.TimeoutExpired(cmd="claude", timeout=60)
            # ruff re-check after claude — won't be reached
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="",
                stderr="",
            )

        mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            side_effect=side_effect,
        )

        errors = _make_errors("app.py", ["E722"])
        warnings: list[str] = []
        remaining = claude_fix(project, errors, warnings=warnings)

        assert remaining == errors
        assert any("timed out" in w for w in warnings)


class TestWarningsInResult:
    """AC3: data['warnings'] reports skipped steps."""

    def test_warnings_in_result(
        self,
        tool: BatchEditTool,
        py_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("axm_edit.services.lint._has_ruff", False)

        result = tool.execute(
            path=str(py_project),
            operations=[_replace_op("hello.py", "x = 1", "x = 2")],
        )

        assert result.success
        assert result.data is not None
        warnings = result.data.get("warnings", [])
        assert any("ruff not found" in w for w in warnings)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestBothToolsMissing:
    """Both ruff and claude missing -> batch_edit works, warnings emitted."""

    def test_both_tools_missing(
        self,
        tool: BatchEditTool,
        py_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("axm_edit.services.lint._has_ruff", False)
        monkeypatch.setattr("axm_edit.services.lint._has_claude", False)

        result = tool.execute(
            path=str(py_project),
            operations=[_replace_op("hello.py", "x = 1", "x = 2")],
        )

        assert result.success
        assert (py_project / "hello.py").read_text().strip() == "x = 2"
        warnings = result.data.get("warnings", []) if result.data else []
        assert any("ruff not found" in w for w in warnings)


class TestRuffWrongVersion:
    """Ruff exists but crashes on invocation -> graceful skip with warning."""

    def test_ruff_wrong_version(
        self,
        tool: BatchEditTool,
        py_project: Path,
        mocker: Any,
    ) -> None:
        mocker.patch(
            "axm_edit.tools.batch_edit.claude_fix",
            side_effect=lambda root, errors, **kw: errors,
        )

        def ruff_oserror(
            cmd: list[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            if isinstance(cmd, list) and "ruff" in cmd:
                raise OSError("ruff: invalid option")
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="",
                stderr="",
            )

        mocker.patch(
            "axm_edit.tools.batch_edit.subprocess.run",
            side_effect=ruff_oserror,
        )

        result = tool.execute(
            path=str(py_project),
            operations=[_replace_op("hello.py", "x = 1", "x = 2")],
        )

        assert result.success
        assert result.data is not None
        warnings = result.data.get("warnings", [])
        assert any("ruff fix failed" in w for w in warnings)


class TestPermissionDenied:
    """Ruff exists but not executable -> graceful skip with warning."""

    def test_permission_denied(
        self,
        tool: BatchEditTool,
        py_project: Path,
        mocker: Any,
    ) -> None:
        mocker.patch(
            "axm_edit.tools.batch_edit.claude_fix",
            side_effect=lambda root, errors, **kw: errors,
        )

        def perm_denied(
            cmd: list[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            if isinstance(cmd, list) and "ruff" in cmd:
                raise PermissionError("Permission denied: ruff")
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="",
                stderr="",
            )

        mocker.patch(
            "axm_edit.tools.batch_edit.subprocess.run",
            side_effect=perm_denied,
        )

        result = tool.execute(
            path=str(py_project),
            operations=[_replace_op("hello.py", "x = 1", "x = 2")],
        )

        assert result.success
        assert result.data is not None
        warnings = result.data.get("warnings", [])
        assert any("ruff fix failed" in w for w in warnings)
