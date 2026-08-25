"""Split from ``test_batch_apply_fuzzy_matching.py``."""

from __future__ import annotations

import pathlib
from collections.abc import Callable
from pathlib import Path

import pytest

from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import CreateOp, Edit, ReplaceOp


def test_multi_file_fuzzy(tmp_project: Path) -> None:
    """Fuzzy matching across multiple files in one batch."""
    ops = [
        ReplaceOp(
            file="src/foo.py",
            edits=[
                # Off by 1 — import os is at L1, hint says L2
                Edit(
                    line=2,
                    old="import os",
                    new="import pathlib",
                ),
            ],
        ),
        ReplaceOp(
            file="src/bar.py",
            edits=[
                # No line hint at all
                Edit(old="import foo", new="import baz"),
            ],
        ),
    ]
    result = batch_apply(tmp_project, ops)
    assert result.success
    foo = (tmp_project / "src" / "foo.py").read_text()
    bar = (tmp_project / "src" / "bar.py").read_text()
    assert "import pathlib" in foo
    assert "import baz" in bar
    assert result.summary["modified"] == 2


class TestMergeSameFile:
    """Tests for merging edits from multiple ReplaceOps."""

    def test_two_replace_ops_same_file(self, tmp_project: Path) -> None:
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(line=1, old="import os", new="import pathlib"),
                ],
            ),
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(line=2, old="import sys", new="import json"),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "foo.py").read_text()
        assert "import pathlib" in content
        assert "import json" in content
        # Merged into 1 file modification
        assert result.summary["modified"] == 1


# ---------------------------------------------------------------------------
# Merged: mid-batch write failure rolls back earlier-touched replace edits.
# ---------------------------------------------------------------------------


def _make_write_text_failer(fail_on_call: int) -> Callable[..., int]:
    """Return a ``Path.write_text`` replacement that raises on the Nth call."""
    real_write_text = pathlib.Path.write_text
    state = {"calls": 0}

    def fake_write_text(self: Path, *args: object, **kwargs: object) -> int:
        state["calls"] += 1
        if state["calls"] == fail_on_call:
            raise OSError("injected write failure")
        return real_write_text(self, *args, **kwargs)

    return fake_write_text


def test_apply_failure_rolls_back_earlier_ops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mid-batch write failure restores earlier-touched files.

    Two replace ops succeed (write_text calls 1 and 2), the third write
    (a create) raises; the two modified files must be restored to their
    pre-batch content and the result must report failure.
    """
    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"
    file_a.write_text("original A\n", encoding="utf-8")
    file_b.write_text("original B\n", encoding="utf-8")

    operations = [
        ReplaceOp(file="a.txt", edits=[Edit(old="original A", new="changed A")]),
        ReplaceOp(file="b.txt", edits=[Edit(old="original B", new="changed B")]),
        CreateOp(file="c.txt", content="new C\n"),
    ]

    # Fail on the 3rd write_text (the create after the two replaces).
    monkeypatch.setattr(
        pathlib.Path, "write_text", _make_write_text_failer(fail_on_call=3)
    )

    result = batch_apply(tmp_path, operations)

    assert result.success is False
    assert result.error
    # Earlier ops rolled back to pre-batch state.
    assert file_a.read_text(encoding="utf-8") == "original A\n"
    assert file_b.read_text(encoding="utf-8") == "original B\n"
