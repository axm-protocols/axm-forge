"""Unit tests for axm_edit.tools.batch_edit_check (no real I/O)."""

from __future__ import annotations

from axm_edit.models.check import CheckDiagnostic
from axm_edit.models.operations import CreateOp, DeleteOp, ReplaceOp
from axm_edit.tools.batch_edit_check import _parse_check_operations, render_text


class TestParseCheckOperations:
    """AC5: the checker reuses the shared operation models."""

    def test_parse_returns_shared_operation_models(self) -> None:
        """AC5: raw dicts map to ReplaceOp / CreateOp / DeleteOp instances."""
        raw_ops: list[dict[str, object]] = [
            {
                "op": "replace",
                "file": "pkg/mod.py",
                "edits": [{"old": "value = 1", "new": "value = 2"}],
            },
            {"op": "create", "file": "pkg/new_mod.py", "content": "value = 3\n"},
            {"op": "delete", "file": "pkg/legacy.py"},
        ]

        parsed = _parse_check_operations(raw_ops)

        assert [type(op) for op in parsed] == [ReplaceOp, CreateOp, DeleteOp]
        replace_op, create_op, delete_op = parsed
        assert isinstance(replace_op, ReplaceOp)
        assert replace_op.file == "pkg/mod.py"
        assert isinstance(create_op, CreateOp)
        assert create_op.content == "value = 3\n"
        assert isinstance(delete_op, DeleteOp)
        assert delete_op.file == "pkg/legacy.py"


class TestRenderText:
    """AC6, AC7: the rendering contract consumed by the CLI."""

    def test_render_text_exposes_code_and_hint_of_each_diagnostic(self) -> None:
        """AC6: every diagnostic surfaces both its code and its hint."""
        diagnostics = [
            CheckDiagnostic(
                op_index=0,
                file="pkg/mod.py",
                severity="error",
                code="CREATE_ON_EXISTING",
                message="`create` targets 'pkg/mod.py', which already exists.",
                hint="Use an op=replace instead of an op=create.",
            ),
            CheckDiagnostic(
                op_index=1,
                file="pkg/other.py",
                severity="error",
                code="UNKNOWN_EDIT_KEY",
                message="unknown edit key(s): olds",
                hint="Drop the extra keys from the edit.",
            ),
        ]

        text = render_text(diagnostics)

        assert "CREATE_ON_EXISTING" in text
        assert "Use an op=replace instead of an op=create." in text
        assert "UNKNOWN_EDIT_KEY" in text
        assert "Drop the extra keys from the edit." in text

    def test_render_text_on_empty_list_announces_zero_diagnostics(self) -> None:
        """AC7: the empty rendering carries the literal `0 diagnostic(s)`."""
        text = render_text([])

        assert "0 diagnostic(s)" in text
