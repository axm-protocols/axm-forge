"""Unit tests for axm_edit.tools.batch_edit — BatchEditTool (no real I/O)."""

from __future__ import annotations

from pathlib import Path

from pytest_mock import MockerFixture

from axm_edit.models.operations import (
    BatchResult,
    CreateOp,
    DeleteOp,
    Edit,
    ReplaceOp,
    ValidationError,
)
from axm_edit.tools.batch_edit import BatchEditTool, _apply_lint, render_text


def _ok_result() -> BatchResult:
    return BatchResult(
        success=True,
        applied=1,
        summary={"modified": 1, "created": 0, "deleted": 0},
    )


class TestBatchEditTool:
    """Tests for the BatchEditTool AXMTool wrapper."""

    def test_name(self) -> None:
        tool = BatchEditTool()
        assert tool.name == "batch_edit"

    def test_execute_no_operations(self) -> None:
        tool = BatchEditTool()
        result = tool.execute(path=".")
        assert not result.success
        assert "No operations" in (result.error or "")

    def test_execute_bad_path(self) -> None:
        tool = BatchEditTool()
        result = tool.execute(
            path="/nonexistent/path",
            operations=[{"op": "delete", "file": "foo.py"}],
        )
        assert not result.success


class TestRenderText:
    """Tests for the ``render_text`` compact rendering helper."""

    def test_success_header_and_per_file_op_lines(self) -> None:
        result = BatchResult(
            success=True,
            applied=3,
            summary={"modified": 1, "created": 1, "deleted": 1},
        )
        parsed = [
            ReplaceOp(file="a.py", edits=[Edit(old="x", new="y")]),
            CreateOp(file="new.py", content="z = 1\n"),
            DeleteOp(file="old.py"),
        ]
        text = render_text(result, parsed, {})
        assert "batch_edit | ✓ |" in text
        assert "1 modified · 1 created · 1 deleted · 3 edits" in text
        assert "~ a.py (1 edit)" in text
        assert "+ new.py" in text
        assert "- old.py" in text

    def test_failure_surfaces_rollback_and_validation_errors(self) -> None:
        result = BatchResult(
            success=False,
            error="Validation failed",
            details=[
                ValidationError(
                    file="a.py",
                    expected="NOPE",
                    error="Content not found",
                )
            ],
        )
        parsed = [
            ReplaceOp(file="a.py", edits=[Edit(old="NOPE", new="y")]),
        ]
        text = render_text(result, parsed, {})
        assert "✗ ROLLBACK" in text
        assert "Validation failed" in text
        assert "a.py: Content not found" in text
        assert "expected: NOPE" in text

    def test_lint_summary_errors_and_diffs_are_rendered(self) -> None:
        result = BatchResult(
            success=True,
            applied=1,
            summary={"modified": 0, "created": 1, "deleted": 0},
        )
        parsed = [CreateOp(file="lintme.py", content="import os\n")]
        data: dict[str, object] = {
            "lint": {"auto_fixed": 2, "remaining": 1},
            "lint_errors": ["lintme.py:1: E999 boom"],
            "warnings": ["ruff slow"],
            "lint_diffs": [
                {"file": "lintme.py", "rules": ["F401"], "diff": "@L1\n-import os"}
            ],
        }
        text = render_text(result, parsed, data)
        assert "lint: 2 auto-fixed · 1 remaining" in text
        assert "! lintme.py:1: E999 boom" in text
        assert "⚠ ruff slow" in text
        assert "lintme.py [F401]" in text
        assert "-import os" in text


class TestImportRemovalAlert:
    """AC1-AC4: dangerous F401/F811 removals surface a leading alert block."""

    def test_f401_removal_produces_leading_alert(self, mocker: MockerFixture) -> None:
        """AC1: an F401 removal prepends an alert naming import/file/code."""
        mocker.patch(
            "axm_edit.tools.batch_edit._run_ruff",
            return_value=(["mod.py:1:8: F401 [*] `os` imported but unused"], []),
        )
        data: dict[str, object] = {}
        _apply_lint(
            Path("/tmp/proj"), [], data, lint_diff=False, lint_diff_max_ratio=0.5
        )

        text = render_text(_ok_result(), [], data)
        first = text.splitlines()[0]
        assert first.startswith("⚠")
        assert "`os`" in first
        assert "mod.py" in first
        assert "F401" in first

    def test_f811_removal_produces_leading_alert(self, mocker: MockerFixture) -> None:
        """AC2: an F811 removal prepends an alert naming symbol/file/code."""
        mocker.patch(
            "axm_edit.tools.batch_edit._run_ruff",
            return_value=(
                ["mod.py:3:1: F811 redefinition of unused `foo` from line 1"],
                [],
            ),
        )
        data: dict[str, object] = {}
        _apply_lint(
            Path("/tmp/proj"), [], data, lint_diff=False, lint_diff_max_ratio=0.5
        )

        text = render_text(_ok_result(), [], data)
        first = text.splitlines()[0]
        assert first.startswith("⚠")
        assert "`foo`" in first
        assert "mod.py" in first
        assert "F811" in first

    def test_clean_batch_produces_no_alert(self, mocker: MockerFixture) -> None:
        """AC3: no F401/F811 removal → no alert block (no false positive)."""
        mocker.patch(
            "axm_edit.tools.batch_edit._run_ruff",
            return_value=(["mod.py:1:1: I001 [*] import block un-sorted"], []),
        )
        data: dict[str, object] = {}
        _apply_lint(
            Path("/tmp/proj"), [], data, lint_diff=False, lint_diff_max_ratio=0.5
        )

        text = render_text(_ok_result(), [], data)
        assert "import_removals" not in data
        assert text.startswith("batch_edit | ✓")
        assert "⚠ lint removed" not in text

    def test_full_diff_remains_below_alert(self, mocker: MockerFixture) -> None:
        """AC4: alert is additive — lint_diffs and the diff stay verbatim below."""
        mocker.patch(
            "axm_edit.tools.batch_edit._run_ruff",
            return_value=(["mod.py:1:8: F401 [*] `os` imported but unused"], []),
        )
        mocker.patch(
            "axm_edit.tools.batch_edit._snapshot_files",
            side_effect=[
                {"mod.py": "import os\nx = 1\n"},
                {"mod.py": "x = 1\n"},
            ],
        )
        data: dict[str, object] = {}
        _apply_lint(
            Path("/tmp/proj"),
            [Path("/tmp/proj/mod.py")],
            data,
            lint_diff=True,
            lint_diff_max_ratio=0.5,
        )

        parsed = [CreateOp(file="mod.py", content="x = 1\n")]
        text = render_text(_ok_result(), parsed, data)
        lines = text.splitlines()

        # Alert leads the block…
        assert lines[0].startswith("⚠")
        # …and the pre-existing lint_diffs content is still present verbatim below.
        assert "lint_diffs" in data
        assert "mod.py [F401]" in text
        assert "-import os" in text
        assert any(line.startswith("batch_edit | ✓") for line in lines)


def _stripped_lines(text: str) -> list[str]:
    """Rendered lines with their indentation removed.

    An editor / quickfix parser only recognises a position when the
    ``{file}:{line}:`` locator *prefixes* the line, so the assertions below
    look at the first token of each line, not at a substring of the blob.
    """
    return [line.lstrip() for line in text.splitlines()]


class TestRenderErrorLocators:
    """AC1-AC3: every validation error is prefixed by a navigable locator."""

    def test_located_error_line_is_prefixed_by_file_line_locator(self) -> None:
        """AC1: line=4 renders a line starting with the ``pkg/mod.py:4:`` token."""
        result = BatchResult(
            success=False,
            error="Validation failed",
            details=[
                ValidationError(
                    file="pkg/mod.py",
                    line=4,
                    expected="value = 1",
                    error="closest line 4 differs: value<NBSP>= 1",
                )
            ],
        )

        text = render_text(result, [], {})

        assert any(ln.startswith("pkg/mod.py:4:") for ln in _stripped_lines(text)), text
        assert "<NBSP>" in text

    def test_unlocated_error_line_carries_no_line_number(self) -> None:
        """AC2: line=None degrades the locator to ``pkg/mod.py:``, no 0, no None."""
        result = BatchResult(
            success=False,
            error="Validation failed",
            details=[
                ValidationError(
                    file="pkg/mod.py",
                    line=None,
                    error="no similar line found in the file",
                )
            ],
        )

        text = render_text(result, [], {})

        assert any(ln.startswith("pkg/mod.py:") for ln in _stripped_lines(text)), text
        assert "pkg/mod.py:0:" not in text
        assert "None" not in text

    def test_one_locator_prefixed_line_per_error_in_order(self) -> None:
        """AC3: two errors render two locator-prefixed lines, in details order."""
        result = BatchResult(
            success=False,
            error="Validation failed",
            details=[
                ValidationError(file="a/x.py", line=4, error="first mismatch"),
                ValidationError(file="b/y.py", line=11, error="second mismatch"),
            ],
        )

        text = render_text(result, [], {})
        located = [
            ln
            for ln in _stripped_lines(text)
            if ln.startswith(("a/x.py:4:", "b/y.py:11:"))
        ]

        assert len(located) == 2, text
        assert located[0].startswith("a/x.py:4:")
        assert located[1].startswith("b/y.py:11:")
