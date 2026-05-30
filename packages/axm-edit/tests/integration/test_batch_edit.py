"""Integration tests for axm_edit.tools.batch_edit — BatchEditTool (real I/O)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from axm_edit.tools.batch_edit import BatchEditTool


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


def _replace_op(file: str, old: str, new: str) -> dict[str, Any]:
    return {"op": "replace", "file": file, "edits": [{"old": old, "new": new}]}


class TestBatchEditTool:
    """Tests for the BatchEditTool AXMTool wrapper."""

    def test_execute_replace(self, tmp_project: Path) -> None:
        tool = BatchEditTool()
        result = tool.execute(
            path=str(tmp_project),
            operations=[
                {
                    "op": "replace",
                    "file": "src/foo.py",
                    "edits": [{"line": 1, "old": "import os", "new": "import pathlib"}],
                },
            ],
        )
        assert result.success
        assert result.data["applied"] == 1

    def test_execute_create(self, tmp_project: Path) -> None:
        tool = BatchEditTool()
        result = tool.execute(
            path=str(tmp_project),
            operations=[
                {"op": "create", "file": "new.py", "content": "hello\n"},
            ],
        )
        assert result.success
        assert (tmp_project / "new.py").exists()

    def test_execute_validation_error(self, tmp_project: Path) -> None:
        tool = BatchEditTool()
        result = tool.execute(
            path=str(tmp_project),
            operations=[
                {
                    "op": "replace",
                    "file": "src/foo.py",
                    "edits": [{"line": 1, "old": "WRONG", "new": "b"}],
                },
            ],
        )
        assert not result.success
        assert result.error is not None

    def test_execute_unknown_op(self, tmp_project: Path) -> None:
        tool = BatchEditTool()
        result = tool.execute(
            path=str(tmp_project),
            operations=[{"op": "unknown", "file": "foo.py"}],
        )
        assert not result.success
        assert "Unknown" in (result.error or "")


# ---------------------------------------------------------------------------
# Graceful degradation (split from ``test_graceful_degradation.py``)
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


class TestRuffInvocationFails:
    """Ruff exists but raises on invocation -> graceful skip with warning."""

    @pytest.mark.parametrize(
        "exc",
        [
            pytest.param(OSError("ruff: invalid option"), id="wrong_version"),
            pytest.param(
                PermissionError("Permission denied: ruff"), id="permission_denied"
            ),
        ],
    )
    def test_ruff_invocation_fails(
        self,
        tool: BatchEditTool,
        py_project: Path,
        mocker: Any,
        exc: Exception,
    ) -> None:
        mocker.patch(
            "axm_edit.tools.batch_edit.claude_fix",
            side_effect=lambda root, errors, **kw: errors,
        )

        def ruff_raises(
            cmd: list[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            if isinstance(cmd, list) and "ruff" in cmd:
                raise exc
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="",
                stderr="",
            )

        mocker.patch(
            "axm_edit.tools.batch_edit.subprocess.run",
            side_effect=ruff_raises,
        )

        result = tool.execute(
            path=str(py_project),
            operations=[_replace_op("hello.py", "x = 1", "x = 2")],
        )

        assert result.success
        assert result.data is not None
        warnings = result.data.get("warnings", [])
        assert any("ruff fix failed" in w for w in warnings)
