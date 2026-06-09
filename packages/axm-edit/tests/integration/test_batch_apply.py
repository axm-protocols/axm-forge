"""Integration tests for utf-8 encoding correctness in the edit engine.

Exercised through the public ``batch_apply`` boundary (not the private
``_apply_replace`` / ``_validate_replace`` helpers).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.core import engine
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


def test_replace_aborts_when_file_drifts_between_validate_and_apply(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: file content at the resolved range drifts after validation.

    The edit must NOT be spliced at the now-stale line location, and the
    batch must report failure for that edit (no silent wrong-location
    splice).
    """
    target = tmp_path / "mod.py"
    target.write_text("line_a\nANCHOR\nline_c\n", encoding="utf-8")

    # Simulate the TOCTOU window: mutate the file on disk after validation
    # has resolved the line of ``ANCHOR`` (line 2) but before the splice.
    # The drift prepends a line so the resolved index now points at
    # ``line_a`` instead of ``ANCHOR``.
    drifted = "inserted_top\nline_a\nANCHOR\nline_c\n"
    real_apply = engine._apply_replace

    def drifting_apply(root: Path, file_rel: str, resolved: object) -> int:
        target.write_text(drifted, encoding="utf-8")
        return real_apply(root, file_rel, resolved)

    monkeypatch.setattr(engine, "_apply_replace", drifting_apply)

    result = batch_apply(
        tmp_path,
        [ReplaceOp(file="mod.py", edits=[Edit(old="ANCHOR", new="REPLACED")])],
    )

    # The stale line 2 (``line_a``) must not have been clobbered by REPLACED.
    final = target.read_text(encoding="utf-8").splitlines()
    assert final != ["inserted_top", "REPLACED", "ANCHOR", "line_c"]
    assert "line_a" in final
    # The batch surfaces the drift as a failure rather than silently splicing.
    assert result.success is False


def test_replace_unchanged_file_applies_normally(tmp_path: Path) -> None:
    """AC3: file untouched between validate and apply applies as before."""
    target = tmp_path / "mod.py"
    target.write_text("line_a\nANCHOR\nline_c\n", encoding="utf-8")

    result = batch_apply(
        tmp_path,
        [ReplaceOp(file="mod.py", edits=[Edit(old="ANCHOR", new="REPLACED")])],
    )

    assert result.success is True
    assert target.read_text(encoding="utf-8") == "line_a\nREPLACED\nline_c\n"
