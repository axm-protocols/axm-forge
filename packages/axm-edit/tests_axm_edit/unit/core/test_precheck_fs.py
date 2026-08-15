"""Unit mirror of :mod:`axm_edit.core.precheck_fs` (pure checks only).

Only the pure function ``check_line_length`` is exercised here: it takes the
replacement text and the resolved limit as arguments and touches no disk.
"""

from __future__ import annotations

from axm_edit.core.precheck import run_static_checks
from axm_edit.core.precheck_fs import check_line_length
from axm_edit.models.operations import ReplaceOp


def test_line_over_default_but_within_limit_is_flagged() -> None:
    """AC6: a 95-char line under a limit of 100 warns about the 88 default."""
    new = "x" * 95

    diagnostics = check_line_length(0, "a.py", new, 100)

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "LINE_LENGTH_DEFAULT_MISMATCH"
    assert diagnostics[0].severity == "warning"


def test_short_or_over_limit_lines_are_not_flagged() -> None:
    """AC6: a line fitting in 88, or exceeding the limit, is not flagged."""
    assert check_line_length(0, "a.py", "x" * 80, 100) == []

    codes = [d.code for d in check_line_length(1, "a.py", "x" * 120, 100)]

    assert "LINE_LENGTH_DEFAULT_MISMATCH" not in codes


def test_edit_index_survives_the_raw_mapping_parse_layer() -> None:
    """AC6: an op parsed from a raw mapping still names the faulty edit slot."""
    raw_op: dict[str, object] = {
        "op": "replace",
        "file": "a.py",
        "edits": [
            {"old": "    return 1", "new": "    return 2"},
            {"old": 'x = """doc"""', "new": "x = 1"},
        ],
    }
    operations = [ReplaceOp.model_validate(raw_op)]
    contents = {"a.py": ["def f():", "    return 1", ""]}

    diagnostics = run_static_checks(operations, contents)

    assert len(diagnostics) == 1
    assert diagnostics[0].edit_index == 1
