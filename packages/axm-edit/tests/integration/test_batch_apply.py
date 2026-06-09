"""Integration tests for utf-8 encoding correctness in the edit engine.

Exercised through the public ``batch_apply`` boundary (not the private
``_apply_replace`` / ``_validate_replace`` helpers).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import CreateOp, Edit, ReplaceOp

pytestmark = pytest.mark.integration


def test_replace_preserves_non_ascii_utf8(tmp_path: Path) -> None:
    """AC1, AC2, AC3: a replace round-trip preserves non-ASCII bytes exactly."""
    target = tmp_path / "sample.txt"
    original = "alpha\nremplacer\nomega\n"
    target.write_text(original, encoding="utf-8")

    result = batch_apply(
        tmp_path,
        [
            ReplaceOp(
                file="sample.txt",
                edits=[Edit(old="remplacer", new="café → 中文")],
            )
        ],
    )

    assert result.success, result

    raw = target.read_bytes()
    text = raw.decode("utf-8")
    assert "café" in text
    assert "→" in text
    assert "中文" in text
    # Exact byte fidelity for the spliced non-ASCII content.
    assert "café → 中文".encode() in raw


def test_create_writes_utf8(tmp_path: Path) -> None:
    """AC2, AC3: a create op writes content as utf-8, readable back identically."""
    content = "élément → 日本語\n"

    result = batch_apply(
        tmp_path,
        [CreateOp(file="created.txt", content=content)],
    )

    assert result.success, result

    created = tmp_path / "created.txt"
    assert created.read_text(encoding="utf-8") == content
