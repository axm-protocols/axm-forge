"""Integration tests for lint_diffs surfaced in BatchEditTool result."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from axm_edit.tools.batch_edit import BatchEditTool

pytestmark = pytest.mark.integration


@pytest.fixture
def tool() -> BatchEditTool:
    return BatchEditTool()


@pytest.fixture
def py_project(tmp_path: Path) -> Path:
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


def _replace_op(file: str, old: str, new: str) -> dict[str, Any]:
    return {"op": "replace", "file": file, "edits": [{"old": old, "new": new}]}


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
        py_project: Path,
    ) -> None:
        (py_project / "hello.py").write_text("import os\nx = 1\n")
        _commit_all(py_project, "unused")

        result = tool.execute(
            path=str(py_project),
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
        py_project: Path,
    ) -> None:
        result = tool.execute(
            path=str(py_project),
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
        py_project: Path,
    ) -> None:
        (py_project / "hello.py").write_text("import os\nx = 1\n")
        _commit_all(py_project, "unused")

        result = tool.execute(
            path=str(py_project),
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
        py_project: Path,
    ) -> None:
        result = tool.execute(
            path=str(py_project),
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
        py_project: Path,
    ) -> None:
        # Many unused imports — ruff strips them all, yielding a large
        # diff relative to the (tiny) surviving file content.
        unused = "\n".join(f"import unused_module_name_{i:03d}" for i in range(12))
        (py_project / "hello.py").write_text(unused + "\nx = 1\n")
        _commit_all(py_project, "messy")

        result = tool.execute(
            path=str(py_project),
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
        py_project: Path,
    ) -> None:
        (py_project / "a.py").write_text("import os\nv = 1\n")
        (py_project / "b.py").write_text("import sys\nw = 1\n")
        _commit_all(py_project, "two unused")

        result = tool.execute(
            path=str(py_project),
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
        py_project: Path,
    ) -> None:
        result = tool.execute(
            path=str(py_project),
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
