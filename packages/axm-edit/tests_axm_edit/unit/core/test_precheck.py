"""Unit tests for axm_edit.core.precheck — pure in-memory static checks."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import cast

from axm_edit.core import precheck
from axm_edit.core.precheck import (
    check_anchor_quotes,
    check_anchor_whole_line,
    check_edit_keys,
    run_static_checks,
)
from axm_edit.models.check import CheckDiagnostic
from axm_edit.models.operations import Edit, ReplaceOp

_RewriteKeyCheck = Callable[[int, str, Mapping[str, object]], list[CheckDiagnostic]]


def _rewrite_key_check() -> _RewriteKeyCheck:
    """Resolve the pure rewrite key check this ticket must expose."""
    check = getattr(precheck, "check_rewrite_keys", None)
    assert callable(check), (
        "axm_edit.core.precheck must expose check_rewrite_keys(op_index, file, raw_op)"
    )
    return cast("_RewriteKeyCheck", check)


class TestCheckEditKeys:
    """AC2: unknown edit keys are reported against the Edit schema."""

    def test_unknown_key_reports_unknown_edit_key_and_lists_allowed_keys(
        self,
    ) -> None:
        """AC2: an out-of-schema key yields UNKNOWN_EDIT_KEY naming the culprit."""
        raw_edit = {"old": "a", "new": "b", "expected_count": 2}

        diagnostics = check_edit_keys(0, "a.py", raw_edit)

        assert len(diagnostics) == 1
        diagnostic = diagnostics[0]
        assert diagnostic.code == "UNKNOWN_EDIT_KEY"
        assert diagnostic.severity == "error"
        assert diagnostic.op_index == 0
        assert diagnostic.file == "a.py"
        assert "expected_count" in diagnostic.message
        for allowed in Edit.model_fields:
            assert allowed in diagnostic.message

    def test_conforming_edit_produces_no_key_diagnostic(self) -> None:
        """AC2: a mapping holding only Edit keys is clean."""
        assert check_edit_keys(0, "a.py", {"old": "a", "new": "b"}) == []


class TestCheckAnchorQuotes:
    """AC3: triple-quoted anchors are rejected."""

    def test_triple_quoted_anchor_reports_anchor_triple_quote(self) -> None:
        """AC3: an old containing \"\"\" yields ANCHOR_TRIPLE_QUOTE."""
        diagnostics = check_anchor_quotes(1, "a.py", 'def f():\n    """doc"""')

        assert len(diagnostics) == 1
        assert diagnostics[0].code == "ANCHOR_TRIPLE_QUOTE"
        assert diagnostics[0].severity == "error"
        assert diagnostics[0].op_index == 1

    def test_quote_free_anchor_produces_nothing(self) -> None:
        """AC3: an anchor without triple-quotes is clean."""
        assert check_anchor_quotes(0, "a.py", "x = 1") == []


class TestCheckAnchorWholeLine:
    """AC4: multi-line anchors must fall on line boundaries."""

    def test_multiline_anchor_cutting_a_line_reports_not_whole_line(self) -> None:
        """AC4: an anchor starting mid-line yields ANCHOR_NOT_WHOLE_LINE."""
        lines = ["def f():", "    return 1", ""]

        diagnostics = check_anchor_whole_line(0, "a.py", lines, "f():\n    return")

        assert len(diagnostics) == 1
        assert diagnostics[0].code == "ANCHOR_NOT_WHOLE_LINE"
        assert diagnostics[0].severity == "error"

    def test_multiline_anchor_on_boundaries_produces_nothing(self) -> None:
        """AC4: both frontiers aligned on the given lines is clean."""
        lines = ["def f():", "    return 1", ""]

        assert check_anchor_whole_line(0, "a.py", lines, "def f():\n    return 1") == []

    def test_single_line_partial_anchor_is_never_flagged(self) -> None:
        """AC4: a mono-line anchor never yields ANCHOR_NOT_WHOLE_LINE."""
        lines = ["def f():", "    return 1", ""]

        assert check_anchor_whole_line(0, "a.py", lines, "return") == []


class TestRunStaticChecks:
    """AC5: the aggregator sorts by op_index and never touches the disk."""

    def test_aggregates_and_sorts_diagnostics_by_op_index(self) -> None:
        """AC5: AC3 + AC4 findings are merged and ordered by op_index."""
        operations = [
            ReplaceOp(file="a.py", edits=[Edit(old="f():\n    return", new="g")]),
            ReplaceOp(file="b.py", edits=[Edit(old='"""doc"""', new="pass")]),
        ]
        contents = {
            "a.py": ["def f():", "    return 1", ""],
            "b.py": ['"""doc"""', ""],
        }

        diagnostics = run_static_checks(operations, contents)

        codes = {d.code for d in diagnostics}
        assert "ANCHOR_NOT_WHOLE_LINE" in codes
        assert "ANCHOR_TRIPLE_QUOTE" in codes
        indexes = [d.op_index for d in diagnostics]
        assert indexes == sorted(indexes)
        assert set(indexes) == {0, 1}


class TestCheckRewriteKeys:
    """AC3: the rewrite payload key contract is validated in memory."""

    def test_unexpected_key_reports_rewrite_unknown_key(self) -> None:
        """AC3: an `overwrite` key yields one blocking rewrite_unknown_key."""
        raw_op: dict[str, object] = {
            "file": "a.py",
            "content": "x = 1\n",
            "checksum": "0" * 64,
            "overwrite": True,
        }

        diagnostics = _rewrite_key_check()(0, "a.py", raw_op)

        assert len(diagnostics) == 1
        diagnostic = diagnostics[0]
        assert diagnostic.code.upper() == "REWRITE_UNKNOWN_KEY"
        assert diagnostic.severity == "error"
        assert diagnostic.op_index == 0
        assert diagnostic.file == "a.py"
        assert "overwrite" in diagnostic.message

    def test_missing_checksum_reports_rewrite_checksum_required(self) -> None:
        """AC3: a rewrite declaring no checksum is blocking."""
        raw_op: dict[str, object] = {"file": "a.py", "content": "x = 1\n"}

        diagnostics = _rewrite_key_check()(1, "a.py", raw_op)

        assert len(diagnostics) == 1
        diagnostic = diagnostics[0]
        assert diagnostic.code.upper() == "REWRITE_CHECKSUM_REQUIRED"
        assert diagnostic.severity == "error"
        assert diagnostic.op_index == 1

    def test_well_formed_rewrite_payload_yields_nothing(self) -> None:
        """AC3: exactly the three expected keys is clean."""
        raw_op: dict[str, object] = {
            "file": "a.py",
            "content": "x = 1\n",
            "checksum": "0" * 64,
        }

        assert _rewrite_key_check()(0, "a.py", raw_op) == []
