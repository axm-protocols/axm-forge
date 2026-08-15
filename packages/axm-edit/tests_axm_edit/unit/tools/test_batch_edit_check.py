"""Unit tests for axm_edit.tools.batch_edit_check (no real I/O)."""

from __future__ import annotations

from axm_edit.core.anchor_rules import ANCHOR_RULES_HINT
from axm_edit.models.check import CheckDiagnostic
from axm_edit.models.operations import CreateOp, DeleteOp, ReplaceOp
from axm_edit.tools.batch_edit_check import (
    BatchEditCheckTool,
    _parse_check_operations,
    render_text,
)

ANCHOR_RULE_MARKERS = (
    "triple quote",
    "trailing newline",
    "whole line",
    "indentation",
)


class TestAgentHintPublishesTheAnchorContract:
    """AC3: the batch_edit_check hint composes the same shared constant."""

    def test_hint_embeds_the_shared_constant_verbatim(self) -> None:
        """AC3: ANCHOR_RULES_HINT is a substring of the checker hint."""
        hint = BatchEditCheckTool().agent_hint

        assert ANCHOR_RULES_HINT in hint, hint

    def test_hint_states_the_four_anchor_rules(self) -> None:
        """AC3: the published checker hint carries the four rule markers."""
        lowered = BatchEditCheckTool().agent_hint.lower()
        missing = [marker for marker in ANCHOR_RULE_MARKERS if marker not in lowered]

        assert not missing, f"missing rule markers: {missing}"


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

    def test_render_text_appends_a_blocking_summary_when_an_error_is_present(
        self,
    ) -> None:
        """AC3: an error diagnostic makes the last line announce blocking."""
        diagnostics = [
            CheckDiagnostic(
                op_index=0,
                file="pkg/mod.py",
                severity="error",
                code="ANCHOR_NOT_FOUND",
                message="Anchor not found in 'pkg/mod.py': 'value = 404'.",
                hint="Re-read the file and copy the anchor verbatim.",
            ),
            CheckDiagnostic(
                op_index=1,
                file="pkg/legacy.py",
                severity="warning",
                code="LINE_LENGTH_DEFAULT_MISMATCH",
                message="Line 1 is 108 chars: over the 88-char default.",
                hint="batch_edit lints with ruff's 88-char default.",
            ),
        ]

        text = render_text(diagnostics)
        lines = text.splitlines()

        assert "ANCHOR_NOT_FOUND" in text
        assert "LINE_LENGTH_DEFAULT_MISMATCH" in text
        assert lines[-1] == "blocking: yes (1 errors, 1 warnings)"

    def test_render_text_reports_a_non_blocking_summary_for_warnings_only(
        self,
    ) -> None:
        """AC3: a warning-only diagnostic list renders `blocking: no`."""
        diagnostics = [
            CheckDiagnostic(
                op_index=0,
                file="pkg/mod.py",
                severity="warning",
                code="ANCHOR_AMBIGUOUS",
                message="Anchor found 2 times in 'pkg/mod.py': 'value'.",
                hint="Extend the anchor with surrounding context.",
            ),
            CheckDiagnostic(
                op_index=1,
                file="pkg/legacy.py",
                severity="warning",
                code="LINE_LENGTH_DEFAULT_MISMATCH",
                message="Line 1 is 108 chars: over the 88-char default.",
                hint="batch_edit lints with ruff's 88-char default.",
            ),
        ]

        text = render_text(diagnostics)
        lines = text.splitlines()

        assert "ANCHOR_AMBIGUOUS" in text
        assert lines[-1] == "blocking: no (0 errors, 2 warnings)"
