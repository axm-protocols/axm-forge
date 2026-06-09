"""Unit tests for axm_edit.tools.batch_edit — BatchEditTool (no real I/O)."""

from __future__ import annotations

from axm_edit.models.operations import (
    BatchResult,
    CreateOp,
    DeleteOp,
    Edit,
    ReplaceOp,
    ValidationError,
)
from axm_edit.tools.batch_edit import BatchEditTool, render_text


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
            "lint": {"auto_fixed": 2, "harness_fixed": 0, "remaining": 1},
            "lint_errors": ["lintme.py:1: E999 boom"],
            "warnings": ["ruff slow"],
            "lint_diffs": [
                {"file": "lintme.py", "rules": ["F401"], "diff": "@L1\n-import os"}
            ],
        }
        text = render_text(result, parsed, data)
        assert "lint: 2 auto-fixed · 0 harness-fixed · 1 remaining" in text
        assert "! lintme.py:1: E999 boom" in text
        assert "⚠ ruff slow" in text
        assert "lintme.py [F401]" in text
        assert "-import os" in text
