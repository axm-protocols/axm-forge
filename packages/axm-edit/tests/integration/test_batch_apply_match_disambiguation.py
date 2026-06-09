"""Integration tests distinguishing not-found from ambiguous replace anchors.

Exercised through the public ``batch_apply`` boundary (not the private
``_scan_all_lines`` / ``_append_not_found_error`` helpers). Asserts on the
returned ``BatchResult`` errors.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import Edit, ReplaceOp

pytestmark = pytest.mark.integration


def test_replace_zero_match_reports_not_found(tmp_path: Path) -> None:
    """AC1, AC4: a zero-match replace reports not-found, never 'ambiguous'."""
    target = tmp_path / "sample.txt"
    target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    operations = [
        ReplaceOp(file="sample.txt", edits=[Edit(old="nonexistent", new="x")]),
    ]

    result = batch_apply(tmp_path, operations)

    assert result.success is False
    assert result.details
    detail = result.details[0]
    assert detail.error is not None
    text = detail.error.lower()
    assert "not" in text and "found" in text
    assert "ambiguous" not in text
    # File untouched.
    assert target.read_text(encoding="utf-8") == "alpha\nbeta\ngamma\n"


def test_replace_multi_match_reports_ambiguous_with_lines(tmp_path: Path) -> None:
    """AC2, AC4: a >=2-match replace reports the count and matching line numbers."""
    target = tmp_path / "sample.txt"
    # 'dup' appears on lines 1, 3 and 5 (1-based).
    target.write_text("dup\nother\ndup\nmore\ndup\n", encoding="utf-8")

    operations = [
        ReplaceOp(file="sample.txt", edits=[Edit(old="dup", new="x")]),
    ]

    result = batch_apply(tmp_path, operations)

    assert result.success is False
    assert result.details
    detail = result.details[0]
    assert detail.error is not None
    text = detail.error.lower()
    assert "ambiguous" in text
    # Count reported.
    assert "3" in detail.error
    # All matching 1-based line numbers reported.
    for line_no in ("1", "3", "5"):
        assert line_no in detail.error
    # Advises disambiguation via a line hint.
    assert "line" in text
    # File untouched.
    assert target.read_text(encoding="utf-8") == "dup\nother\ndup\nmore\ndup\n"


def test_replace_single_match_applies(tmp_path: Path) -> None:
    """AC3: a single-match replace resolves and applies unchanged."""
    target = tmp_path / "sample.txt"
    target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    operations = [
        ReplaceOp(file="sample.txt", edits=[Edit(old="beta", new="BETA")]),
    ]

    result = batch_apply(tmp_path, operations)

    assert result.success is True
    assert not result.details
    assert target.read_text(encoding="utf-8") == "alpha\nBETA\ngamma\n"
