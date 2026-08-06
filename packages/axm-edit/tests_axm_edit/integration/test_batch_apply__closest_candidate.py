"""Integration tests: ``batch_apply`` surfaces near misses on real files."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import Edit, ReplaceOp

# Built from its code point: a raw U+00A0 in the source is unreadable (and
# rightly flagged as an ambiguous character by ruff RUF001).
NBSP = chr(0x00A0)


@pytest.mark.integration
def test_nbsp_near_miss_surfaced_end_to_end(tmp_path: Path) -> None:
    """AC7: a U+00A0-only near miss reports its line and the ``<NBSP>`` marker."""
    target = tmp_path / "mod.py"
    original = (
        f"import os\n\ndef main() -> int:\ntotal{NBSP}= compute(41)\nreturn total\n"
    )
    target.write_text(original, encoding="utf-8")

    result = batch_apply(
        tmp_path,
        [
            ReplaceOp(
                file="mod.py",
                edits=[
                    Edit(old="total = compute(41)", new="total = compute(1)"),
                ],
            )
        ],
    )

    assert result.success is False
    assert result.details
    detail = result.details[0]
    assert detail.line == 4
    assert detail.error is not None
    assert "<NBSP>" in detail.error
    assert target.read_text(encoding="utf-8") == original


@pytest.mark.integration
def test_absent_anchor_reports_no_similar_line(tmp_path: Path) -> None:
    """AC4: a genuinely absent anchor keeps ``line`` unset and says so."""
    target = tmp_path / "sample.txt"
    original = "alpha\nbeta\ngamma\n"
    target.write_text(original, encoding="utf-8")

    result = batch_apply(
        tmp_path,
        [
            ReplaceOp(
                file="sample.txt",
                edits=[Edit(old="ZZZ_MISSING_ANCHOR_TOKEN_123", new="x")],
            )
        ],
    )

    assert result.success is False
    assert result.details
    detail = result.details[0]
    assert detail.line is None
    assert detail.error is not None
    assert "no similar line" in detail.error.lower()
    assert target.read_text(encoding="utf-8") == original
