"""Tests for ruff --fix post-edit integration in BatchEditTool."""

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
    """Create a minimal project with a Python file and git init."""
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


def _create_op(file: str, content: str) -> dict[str, Any]:
    return {"op": "create", "file": file, "content": content}


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestRuffFixRunsOnChangedFiles:
    """batch_edit with unused import -> file auto-fixed, no lint_errors."""

    def test_ruff_fix_runs_on_changed_files(
        self,
        tool: BatchEditTool,
        py_project: Path,
    ) -> None:
        # Write a file with an unused import that ruff --fix can remove
        (py_project / "hello.py").write_text("import os\nx = 1\n")
        subprocess.run(
            ["git", "add", "."],
            cwd=py_project,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "add unused"],
            cwd=py_project,
            capture_output=True,
            check=True,
            env={
                "GIT_AUTHOR_NAME": "t",
                "GIT_COMMITTER_NAME": "t",
                "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_EMAIL": "t@t",
                "HOME": str(py_project),
            },
        )

        result = tool.execute(
            path=str(py_project),
            operations=[_replace_op("hello.py", "x = 1", "x = 2")],
        )

        assert result.success
        assert result.data is not None
        # After ruff fix the unused import should be removed
        content = (py_project / "hello.py").read_text()
        assert "import os" not in content
        # No remaining lint errors
        assert not result.data.get("lint_errors")


class TestRuffCheckReturnsErrors:
    """File with unfixable error -> lint_errors populated in result."""

    def test_ruff_check_returns_errors(
        self,
        tool: BatchEditTool,
        py_project: Path,
        mocker: Any,
    ) -> None:
        # Mock claude_fix to pass through errors (don't spawn real subprocess)
        mocker.patch(
            "axm_edit.tools.batch_edit.claude_fix",
            side_effect=lambda root, errors, **kw: errors,
        )

        # py_project already has hello.py with "x = 1\n" committed
        # Replace with code that has a bare except (E722 - not auto-fixable)
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
        assert result.data.get("lint_errors")


class TestLintFalseSkipsRuff:
    """batch_edit(lint=False) -> no ruff subprocess called."""

    def test_lint_false_skips_ruff(
        self,
        tool: BatchEditTool,
        py_project: Path,
        mocker: Any,
    ) -> None:
        spy = mocker.patch("subprocess.run", wraps=subprocess.run)

        result = tool.execute(
            path=str(py_project),
            operations=[_replace_op("hello.py", "x = 1", "x = 2")],
            lint=False,
        )

        assert result.success
        # Ensure ruff was never called
        for call in spy.call_args_list:
            args = call.args[0] if call.args else call.kwargs.get("args", [])
            if isinstance(args, list):
                assert "ruff" not in args, "ruff should not be called when lint=False"


class TestLintOnlyOnSuccess:
    """Invalid edit (validation fail) -> no ruff subprocess called."""

    def test_lint_only_on_success(
        self,
        tool: BatchEditTool,
        py_project: Path,
        mocker: Any,
    ) -> None:
        spy = mocker.patch("subprocess.run", wraps=subprocess.run)

        # Try to replace text that doesn't exist -> validation failure
        result = tool.execute(
            path=str(py_project),
            operations=[_replace_op("hello.py", "nonexistent text", "new text")],
        )

        assert not result.success
        # Ruff should not have been called on failure
        for call in spy.call_args_list:
            args = call.args[0] if call.args else call.kwargs.get("args", [])
            if isinstance(args, list):
                assert "ruff" not in args, "ruff should not run on failed edits"


class TestRuffUsesProjectConfig:
    """pyproject.toml with custom rules -> ruff respects project config."""

    def test_ruff_uses_project_config(
        self,
        tool: BatchEditTool,
        py_project: Path,
    ) -> None:
        # Create a pyproject.toml that ignores E722 (bare except)
        (py_project / "pyproject.toml").write_text(
            '[tool.ruff.lint]\nignore = ["E722"]\n'
        )
        subprocess.run(
            ["git", "add", "."],
            cwd=py_project,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "add config"],
            cwd=py_project,
            capture_output=True,
            check=True,
            env={
                "GIT_AUTHOR_NAME": "t",
                "GIT_COMMITTER_NAME": "t",
                "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_EMAIL": "t@t",
                "HOME": str(py_project),
            },
        )

        # Replace with bare except — should NOT be flagged because config ignores E722
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
        # E722 should be suppressed by project config
        assert not result.data.get("lint_errors")


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


class TestBatchEditAutoFixesImports:
    """Create file with unsorted imports -> file has sorted imports after edit."""

    def test_batch_edit_auto_fixes_imports(
        self,
        tool: BatchEditTool,
        py_project: Path,
    ) -> None:
        result = tool.execute(
            path=str(py_project),
            operations=[
                _create_op(
                    "new_module.py",
                    "import sys\nimport os\n\nprint(os.getcwd(), sys.argv)\n",
                )
            ],
        )

        assert result.success
        content = (py_project / "new_module.py").read_text()
        # ruff should sort imports: os before sys
        lines = [ln for ln in content.splitlines() if ln.startswith("import ")]
        assert lines == ["import os", "import sys"]


class TestClaudeFixCalledFromBatchEdit:
    """AC1 integration: claude_fix invoked when ruff returns unfixable errors."""

    def test_claude_fix_invoked(
        self,
        tool: BatchEditTool,
        py_project: Path,
        mocker: Any,
    ) -> None:
        mock_claude = mocker.patch(
            "axm_edit.tools.batch_edit.claude_fix",
            return_value=[],  # Simulate claude fixing everything
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
        # claude_fix should have been called with the ruff errors
        mock_claude.assert_called_once()
        call_args = mock_claude.call_args
        assert len(call_args.args[1]) > 0, "claude_fix should receive ruff errors"

    def test_claude_fix_clears_lint_errors(
        self,
        tool: BatchEditTool,
        py_project: Path,
        mocker: Any,
    ) -> None:
        mocker.patch(
            "axm_edit.tools.batch_edit.claude_fix",
            return_value=[],  # Claude fixed everything
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
        assert not result.data.get("lint_errors"), (
            "No lint_errors when claude_fix resolves everything"
        )


class TestBatchEditReportsRemaining:
    """Create file with unfixable ruff error -> lint_errors in ToolResult.data."""

    def test_batch_edit_reports_remaining(
        self,
        tool: BatchEditTool,
        py_project: Path,
        mocker: Any,
    ) -> None:
        mocker.patch(
            "axm_edit.tools.batch_edit.claude_fix",
            side_effect=lambda root, errors, **kw: errors,
        )

        result = tool.execute(
            path=str(py_project),
            operations=[
                _create_op(
                    "bad_module.py",
                    "try:\n    x = 1\nexcept:\n    pass\n",
                )
            ],
        )

        assert result.success
        assert result.data is not None
        assert result.data.get("lint_errors")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestNoPythonFilesSkipsLint:
    """batch_edit on .md/.toml only -> lint step skipped."""

    def test_no_python_files_skips_lint(
        self,
        tool: BatchEditTool,
        py_project: Path,
        mocker: Any,
    ) -> None:
        spy = mocker.patch("subprocess.run", wraps=subprocess.run)

        result = tool.execute(
            path=str(py_project),
            operations=[_create_op("readme.md", "# Hello\n")],
        )

        assert result.success
        # Ruff should not be called for non-Python files
        for call in spy.call_args_list:
            args = call.args[0] if call.args else call.kwargs.get("args", [])
            if isinstance(args, list):
                assert "ruff" not in args, "ruff should not run on non-Python files"


class TestEmptyOperationsNoLint:
    """operations=[] -> no lint run."""

    def test_empty_operations_no_lint(
        self,
        tool: BatchEditTool,
        py_project: Path,
        mocker: Any,
    ) -> None:
        spy = mocker.patch("subprocess.run", wraps=subprocess.run)

        result = tool.execute(
            path=str(py_project),
            operations=[],
        )

        assert not result.success  # empty ops should fail
        # No subprocess calls for ruff
        for call in spy.call_args_list:
            args = call.args[0] if call.args else call.kwargs.get("args", [])
            if isinstance(args, list):
                assert "ruff" not in args


class TestMixedSuccessLintsOnlyEdited:
    """Some files edited, some failed -> only lint edited files."""

    def test_mixed_success_lints_only_edited(
        self,
        tool: BatchEditTool,
        py_project: Path,
    ) -> None:
        # Note: batch_apply is atomic — if any validation fails, none are applied.
        # So on mixed validation failure, no files get edited and no lint runs.
        result = tool.execute(
            path=str(py_project),
            operations=[
                _replace_op("hello.py", "x = 1", "x = 2"),
                _replace_op("hello.py", "nonexistent", "new"),  # will fail
            ],
        )

        # The whole batch fails because of the invalid edit
        assert not result.success
        assert result.data is not None
        # No lint_errors should be present since no files were edited
        assert not result.data.get("lint_errors")


class TestRunRuffFormats:
    """AC1: _run_ruff calls ruff format after ruff check --fix."""

    def test_run_ruff_formats(
        self,
        tool: BatchEditTool,
        py_project: Path,
    ) -> None:
        # Create a file with valid but poorly formatted code
        result = tool.execute(
            path=str(py_project),
            operations=[
                _replace_op(
                    "hello.py",
                    "x = 1",
                    "x={1:2,3:4}",
                )
            ],
        )

        assert result.success
        content = (py_project / "hello.py").read_text()
        # ruff format should have added spaces around = and after colons/commas
        assert "x = {1: 2, 3: 4}" in content


class TestRunRuffCheckStillWorks:
    """AC4: ruff check --fix still auto-fixes lint violations."""

    def test_run_ruff_check_still_works(
        self,
        tool: BatchEditTool,
        py_project: Path,
    ) -> None:
        # Write a file with an unused import
        (py_project / "hello.py").write_text("import os\nx = 1\n")
        subprocess.run(
            ["git", "add", "."],
            cwd=py_project,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "unused"],
            cwd=py_project,
            capture_output=True,
            check=True,
            env={
                "GIT_AUTHOR_NAME": "t",
                "GIT_COMMITTER_NAME": "t",
                "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_EMAIL": "t@t",
                "HOME": str(py_project),
            },
        )

        result = tool.execute(
            path=str(py_project),
            operations=[_replace_op("hello.py", "x = 1", "x = 2")],
        )

        assert result.success
        content = (py_project / "hello.py").read_text()
        assert "import os" not in content
        assert not result.data.get("lint_errors")


class TestRunRuffUsesProjectEnv:
    """AC2: ruff commands use uv run ruff, not bare ruff."""

    def test_run_ruff_uses_uv_run(
        self,
        tool: BatchEditTool,
        py_project: Path,
        mocker: Any,
    ) -> None:
        spy = mocker.patch("subprocess.run", wraps=subprocess.run)

        tool.execute(
            path=str(py_project),
            operations=[_replace_op("hello.py", "x = 1", "x = 2")],
        )

        ruff_calls = [call for call in spy.call_args_list if _has_ruff_in_args(call)]
        for call in ruff_calls:
            args = call.args[0] if call.args else call.kwargs.get("args", [])
            assert args[0:2] == ["uv", "run"], f"Expected 'uv run ruff ...', got {args}"


def _has_ruff_in_args(call: Any) -> bool:
    """Check if a subprocess.run call involves ruff."""
    args = call.args[0] if call.args else call.kwargs.get("args", [])
    return isinstance(args, list) and "ruff" in args
