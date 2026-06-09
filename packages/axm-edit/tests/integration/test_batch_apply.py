"""Integration tests for utf-8 encoding correctness in the edit engine.

Exercised through the public ``batch_apply`` boundary (not the private
``_apply_replace`` / ``_validate_replace`` helpers).
"""

from __future__ import annotations

import pathlib
from collections.abc import Callable
from pathlib import Path

import pytest

from axm_edit.core import engine
from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import CreateOp, DeleteOp, Edit, ReplaceOp

pytestmark = pytest.mark.integration


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
    """AC1, AC2: a mid-batch write failure restores earlier-touched files.

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


def test_apply_failure_removes_batch_created_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: a file created earlier in the batch is removed on rollback.

    The single replace op succeeds (write_text call 1), the create op
    (call 2) succeeds, and a second create (call 3) raises. The first
    created file must no longer exist after the rollback.
    """
    file_a = tmp_path / "a.txt"
    file_a.write_text("original A\n", encoding="utf-8")

    operations = [
        ReplaceOp(file="a.txt", edits=[Edit(old="original A", new="changed A")]),
        CreateOp(file="created.txt", content="first new\n"),
        CreateOp(file="nested/created2.txt", content="second new\n"),
    ]

    # write_text calls: 1=replace a.txt, 2=create created.txt, 3=nested -> fail
    monkeypatch.setattr(
        pathlib.Path, "write_text", _make_write_text_failer(fail_on_call=3)
    )

    result = batch_apply(tmp_path, operations)

    assert result.success is False
    # The batch-created file is gone after rollback.
    assert not (tmp_path / "created.txt").exists()
    # And the replace was restored.
    assert file_a.read_text(encoding="utf-8") == "original A\n"


def test_happy_path_unchanged(tmp_path: Path) -> None:
    """AC4: a normal batch applies fully with success and correct counts."""
    file_a = tmp_path / "a.txt"
    file_a.write_text("original A\n", encoding="utf-8")
    to_delete = tmp_path / "old.txt"
    to_delete.write_text("bye\n", encoding="utf-8")

    operations = [
        ReplaceOp(file="a.txt", edits=[Edit(old="original A", new="changed A")]),
        CreateOp(file="c.txt", content="new C\n"),
        DeleteOp(file="old.txt"),
    ]

    result = batch_apply(tmp_path, operations)

    assert result.success is True
    assert result.summary == {"modified": 1, "created": 1, "deleted": 1}
    assert file_a.read_text(encoding="utf-8") == "changed A\n"
    assert (tmp_path / "c.txt").read_text(encoding="utf-8") == "new C\n"
    assert not to_delete.exists()


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
