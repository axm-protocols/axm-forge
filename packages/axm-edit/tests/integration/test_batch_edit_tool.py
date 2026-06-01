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


@pytest.fixture
def py_project__from_batch_edit_lint_diffs(tmp_path: Path) -> Path:
    """Minimal project with a committed Python file."""
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


def _create_op(file: str, content: str) -> dict[str, Any]:
    return {"op": "create", "file": file, "content": content}


def _commit_all(repo: Path, msg: str) -> None:
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=repo,
        capture_output=True,
        check=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_EMAIL": "t@t",
            "HOME": str(repo),
        },
    )


class TestLintDiffsPresentWhenMutated:
    """AC1, AC3: ruff removes unused import -> lint_diffs entry surfaces."""

    def test_lint_diffs_present_when_ruff_removes_unused_import(
        self,
        tool: BatchEditTool,
        py_project__from_batch_edit_lint_diffs: Path,
    ) -> None:
        (py_project__from_batch_edit_lint_diffs / "hello.py").write_text(
            "import os\nx = 1\n"
        )
        _commit_all(py_project__from_batch_edit_lint_diffs, "unused")

        result = tool.execute(
            path=str(py_project__from_batch_edit_lint_diffs),
            operations=[_replace_op("hello.py", "x = 1", "x = 2")],
        )

        assert result.success
        assert result.data is not None
        lint_diffs = result.data.get("lint_diffs")
        assert lint_diffs, "lint_diffs should be present after ruff mutation"
        assert len(lint_diffs) == 1
        entry = lint_diffs[0]
        assert "F401" in entry["rules"]
        assert "-import os" in entry["diff"]


class TestLintDiffsAbsentWhenNoMutation:
    """AC5: clean edit -> no lint_diffs key."""

    def test_lint_diffs_absent_when_no_mutation(
        self,
        tool: BatchEditTool,
        py_project__from_batch_edit_lint_diffs: Path,
    ) -> None:
        result = tool.execute(
            path=str(py_project__from_batch_edit_lint_diffs),
            operations=[_replace_op("hello.py", "x = 1", "x = 2")],
        )

        assert result.success
        assert result.data is not None
        assert "lint_diffs" not in result.data


class TestLintDiffParamDisables:
    """AC7: lint_diff=False suppresses lint_diffs."""

    def test_lint_diff_param_false_disables_feature(
        self,
        tool: BatchEditTool,
        py_project__from_batch_edit_lint_diffs: Path,
    ) -> None:
        (py_project__from_batch_edit_lint_diffs / "hello.py").write_text(
            "import os\nx = 1\n"
        )
        _commit_all(py_project__from_batch_edit_lint_diffs, "unused")

        result = tool.execute(
            path=str(py_project__from_batch_edit_lint_diffs),
            operations=[_replace_op("hello.py", "x = 1", "x = 2")],
            lint_diff=False,
        )

        assert result.success
        assert result.data is not None
        assert "lint_diffs" not in result.data


class TestLintFalseImpliesNoDiff:
    """AC8: lint=False short-circuits diff calculation."""

    def test_lint_false_implies_no_diff(
        self,
        tool: BatchEditTool,
        py_project__from_batch_edit_lint_diffs: Path,
    ) -> None:
        result = tool.execute(
            path=str(py_project__from_batch_edit_lint_diffs),
            operations=[_replace_op("hello.py", "x = 1", "x = 2")],
            lint=False,
        )

        assert result.success
        assert result.data is not None
        assert "lint_diffs" not in result.data
        assert "lint" not in result.data


class TestLintDiffMaxRatioFallback:
    """AC4, AC6: mutation ratio exceeds max_ratio -> fallback entry."""

    def test_lint_diff_max_ratio_triggers_fallback(
        self,
        tool: BatchEditTool,
        py_project__from_batch_edit_lint_diffs: Path,
    ) -> None:
        # Many unused imports — ruff strips them all, yielding a large
        # diff relative to the (tiny) surviving file content.
        unused = "\n".join(f"import unused_module_name_{i:03d}" for i in range(12))
        (py_project__from_batch_edit_lint_diffs / "hello.py").write_text(
            unused + "\nx = 1\n"
        )
        _commit_all(py_project__from_batch_edit_lint_diffs, "messy")

        result = tool.execute(
            path=str(py_project__from_batch_edit_lint_diffs),
            operations=[_replace_op("hello.py", "x = 1", "x = 2")],
            lint_diff_max_ratio=0.05,
        )

        assert result.success
        assert result.data is not None
        lint_diffs = result.data.get("lint_diffs")
        assert lint_diffs, "lint_diffs should report the mutated file"
        entry = next(e for e in lint_diffs if e["file"].endswith("hello.py"))
        assert entry.get("diff_skipped") == "file_reread_recommended"
        assert "diff" not in entry


class TestMultipleFilesMutated:
    """AC1: each mutated Python file gets its own lint_diffs entry."""

    def test_multiple_files_mutated_each_gets_entry(
        self,
        tool: BatchEditTool,
        py_project__from_batch_edit_lint_diffs: Path,
    ) -> None:
        (py_project__from_batch_edit_lint_diffs / "a.py").write_text(
            "import os\nv = 1\n"
        )
        (py_project__from_batch_edit_lint_diffs / "b.py").write_text(
            "import sys\nw = 1\n"
        )
        _commit_all(py_project__from_batch_edit_lint_diffs, "two unused")

        result = tool.execute(
            path=str(py_project__from_batch_edit_lint_diffs),
            operations=[
                _replace_op("a.py", "v = 1", "v = 2"),
                _replace_op("b.py", "w = 1", "w = 2"),
            ],
        )

        assert result.success
        assert result.data is not None
        lint_diffs = result.data.get("lint_diffs")
        assert lint_diffs is not None
        files = {entry["file"] for entry in lint_diffs}
        assert any(f.endswith("a.py") for f in files)
        assert any(f.endswith("b.py") for f in files)


class TestCreateOpPythonFileInDiff:
    """AC1: op=create of Py file with mutation appears in lint_diffs."""

    def test_create_op_python_file_included_in_diff(
        self,
        tool: BatchEditTool,
        py_project__from_batch_edit_lint_diffs: Path,
    ) -> None:
        result = tool.execute(
            path=str(py_project__from_batch_edit_lint_diffs),
            operations=[
                _create_op("new_mod.py", "import os\nvalue = 42\n"),
            ],
        )

        assert result.success
        assert result.data is not None
        lint_diffs = result.data.get("lint_diffs")
        assert lint_diffs, "lint_diffs should include the created file"
        files = {entry["file"] for entry in lint_diffs}
        assert any(f.endswith("new_mod.py") for f in files)


@pytest.fixture
def py_project__from_batch_edit_lint_integration(tmp_path: Path) -> Path:
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


def _has_ruff_in_args(call: Any) -> bool:
    """Check if a subprocess.run call involves ruff."""
    args = call.args[0] if call.args else call.kwargs.get("args", [])
    return isinstance(args, list) and "ruff" in args


class TestRuffFixRunsOnChangedFiles:
    """batch_edit with unused import -> file auto-fixed, no lint_errors."""

    def test_ruff_fix_runs_on_changed_files(
        self,
        tool: BatchEditTool,
        py_project__from_batch_edit_lint_integration: Path,
    ) -> None:
        # Write a file with an unused import that ruff --fix can remove
        (py_project__from_batch_edit_lint_integration / "hello.py").write_text(
            "import os\nx = 1\n"
        )
        subprocess.run(
            ["git", "add", "."],
            cwd=py_project__from_batch_edit_lint_integration,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "add unused"],
            cwd=py_project__from_batch_edit_lint_integration,
            capture_output=True,
            check=True,
            env={
                "GIT_AUTHOR_NAME": "t",
                "GIT_COMMITTER_NAME": "t",
                "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_EMAIL": "t@t",
                "HOME": str(py_project__from_batch_edit_lint_integration),
            },
        )

        result = tool.execute(
            path=str(py_project__from_batch_edit_lint_integration),
            operations=[_replace_op("hello.py", "x = 1", "x = 2")],
        )

        assert result.success
        assert result.data is not None
        # After ruff fix the unused import should be removed
        content = (
            py_project__from_batch_edit_lint_integration / "hello.py"
        ).read_text()
        assert "import os" not in content
        # No remaining lint errors
        assert not result.data.get("lint_errors")


class TestRuffCheckReturnsErrors:
    """Unfixable error (E722) via replace or create -> lint_errors populated."""

    @pytest.mark.parametrize(
        "operations",
        [
            pytest.param(
                [
                    _replace_op(
                        "hello.py", "x = 1", "try:\n    x = 1\nexcept:\n    pass"
                    )
                ],
                id="replace",
            ),
            pytest.param(
                [_create_op("bad_module.py", "try:\n    x = 1\nexcept:\n    pass\n")],
                id="create",
            ),
        ],
    )
    def test_ruff_check_returns_errors(
        self,
        tool: BatchEditTool,
        py_project__from_batch_edit_lint_integration: Path,
        mocker: Any,
        operations: list[dict[str, Any]],
    ) -> None:
        # Mock claude_fix to pass through errors (don't spawn real subprocess)
        mocker.patch(
            "axm_edit.tools.batch_edit.claude_fix",
            side_effect=lambda root, errors, **kw: errors,
        )

        result = tool.execute(
            path=str(py_project__from_batch_edit_lint_integration),
            operations=operations,
        )

        assert result.success
        assert result.data is not None
        assert result.data.get("lint_errors")


class TestLintFalseSkipsRuff:
    """batch_edit(lint=False) -> no ruff subprocess called."""

    def test_lint_false_skips_ruff(
        self,
        tool: BatchEditTool,
        py_project__from_batch_edit_lint_integration: Path,
        mocker: Any,
    ) -> None:
        spy = mocker.patch("subprocess.run", wraps=subprocess.run)

        result = tool.execute(
            path=str(py_project__from_batch_edit_lint_integration),
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
        py_project__from_batch_edit_lint_integration: Path,
        mocker: Any,
    ) -> None:
        spy = mocker.patch("subprocess.run", wraps=subprocess.run)

        # Try to replace text that doesn't exist -> validation failure
        result = tool.execute(
            path=str(py_project__from_batch_edit_lint_integration),
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
        py_project__from_batch_edit_lint_integration: Path,
    ) -> None:
        # Create a pyproject.toml that ignores E722 (bare except)
        (py_project__from_batch_edit_lint_integration / "pyproject.toml").write_text(
            '[tool.ruff.lint]\nignore = ["E722"]\n'
        )
        subprocess.run(
            ["git", "add", "."],
            cwd=py_project__from_batch_edit_lint_integration,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "add config"],
            cwd=py_project__from_batch_edit_lint_integration,
            capture_output=True,
            check=True,
            env={
                "GIT_AUTHOR_NAME": "t",
                "GIT_COMMITTER_NAME": "t",
                "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_EMAIL": "t@t",
                "HOME": str(py_project__from_batch_edit_lint_integration),
            },
        )

        # Replace with bare except — should NOT be flagged because config ignores E722
        result = tool.execute(
            path=str(py_project__from_batch_edit_lint_integration),
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


class TestBatchEditAutoFixesImports:
    """Create file with unsorted imports -> file has sorted imports after edit."""

    def test_batch_edit_auto_fixes_imports(
        self,
        tool: BatchEditTool,
        py_project__from_batch_edit_lint_integration: Path,
    ) -> None:
        result = tool.execute(
            path=str(py_project__from_batch_edit_lint_integration),
            operations=[
                _create_op(
                    "new_module.py",
                    "import sys\nimport os\n\nprint(os.getcwd(), sys.argv)\n",
                )
            ],
        )

        assert result.success
        content = (
            py_project__from_batch_edit_lint_integration / "new_module.py"
        ).read_text()
        # ruff should sort imports: os before sys
        lines = [ln for ln in content.splitlines() if ln.startswith("import ")]
        assert lines == ["import os", "import sys"]


class TestClaudeFixCalledFromBatchEdit:
    """AC1 integration: claude_fix invoked when ruff returns unfixable errors."""

    def test_claude_fix_invoked(
        self,
        tool: BatchEditTool,
        py_project__from_batch_edit_lint_integration: Path,
        mocker: Any,
    ) -> None:
        mock_claude = mocker.patch(
            "axm_edit.tools.batch_edit.claude_fix",
            return_value=[],  # Simulate claude fixing everything
        )

        result = tool.execute(
            path=str(py_project__from_batch_edit_lint_integration),
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
        py_project__from_batch_edit_lint_integration: Path,
        mocker: Any,
    ) -> None:
        mocker.patch(
            "axm_edit.tools.batch_edit.claude_fix",
            return_value=[],  # Claude fixed everything
        )

        result = tool.execute(
            path=str(py_project__from_batch_edit_lint_integration),
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


class TestNoPythonFilesSkipsLint:
    """batch_edit on .md/.toml only -> lint step skipped."""

    def test_no_python_files_skips_lint(
        self,
        tool: BatchEditTool,
        py_project__from_batch_edit_lint_integration: Path,
        mocker: Any,
    ) -> None:
        spy = mocker.patch("subprocess.run", wraps=subprocess.run)

        result = tool.execute(
            path=str(py_project__from_batch_edit_lint_integration),
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
        py_project__from_batch_edit_lint_integration: Path,
        mocker: Any,
    ) -> None:
        spy = mocker.patch("subprocess.run", wraps=subprocess.run)

        result = tool.execute(
            path=str(py_project__from_batch_edit_lint_integration),
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
        py_project__from_batch_edit_lint_integration: Path,
    ) -> None:
        # Note: batch_apply is atomic — if any validation fails, none are applied.
        # So on mixed validation failure, no files get edited and no lint runs.
        result = tool.execute(
            path=str(py_project__from_batch_edit_lint_integration),
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
        py_project__from_batch_edit_lint_integration: Path,
    ) -> None:
        # Create a file with valid but poorly formatted code
        result = tool.execute(
            path=str(py_project__from_batch_edit_lint_integration),
            operations=[
                _replace_op(
                    "hello.py",
                    "x = 1",
                    "x={1:2,3:4}",
                )
            ],
        )

        assert result.success
        content = (
            py_project__from_batch_edit_lint_integration / "hello.py"
        ).read_text()
        # ruff format should have added spaces around = and after colons/commas
        assert "x = {1: 2, 3: 4}" in content


class TestRunRuffUsesProjectEnv:
    """AC2: ruff commands use uv run ruff, not bare ruff."""

    def test_run_ruff_uses_uv_run(
        self,
        tool: BatchEditTool,
        py_project__from_batch_edit_lint_integration: Path,
        mocker: Any,
    ) -> None:
        spy = mocker.patch("subprocess.run", wraps=subprocess.run)

        tool.execute(
            path=str(py_project__from_batch_edit_lint_integration),
            operations=[_replace_op("hello.py", "x = 1", "x = 2")],
        )

        ruff_calls = [call for call in spy.call_args_list if _has_ruff_in_args(call)]
        for call in ruff_calls:
            args = call.args[0] if call.args else call.kwargs.get("args", [])
            assert args[0:2] == ["uv", "run"], f"Expected 'uv run ruff ...', got {args}"
