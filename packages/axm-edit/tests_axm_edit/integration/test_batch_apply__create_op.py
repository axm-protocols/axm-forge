"""Split from ``test_engine.py``."""

from __future__ import annotations

import pathlib
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import CreateOp, Edit, ReplaceOp

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


class TestCreate:
    """Tests for create operations."""

    def test_create_new_file(self, tmp_project: Path) -> None:
        ops = [CreateOp(file="src/new.py", content='"""New module."""\n')]
        result = batch_apply(tmp_project, ops)
        assert result.success
        path = tmp_project / "src" / "new.py"
        assert path.exists()
        assert path.read_text() == '"""New module."""\n'
        assert result.summary["created"] == 1

    def test_create_existing_fails(self, tmp_project: Path) -> None:
        ops = [CreateOp(file="src/foo.py", content="overwrite")]
        result = batch_apply(tmp_project, ops)
        assert not result.success
        assert any("already exists" in (d.error or "") for d in result.details)

    def test_create_with_overwrite(self, tmp_project: Path) -> None:
        ops = [
            CreateOp(
                file="src/foo.py",
                content="overwritten\n",
                overwrite=True,
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        assert (tmp_project / "src" / "foo.py").read_text() == "overwritten\n"

    def test_create_nested_dirs(self, tmp_project: Path) -> None:
        ops = [CreateOp(file="src/auth/__init__.py", content="")]
        result = batch_apply(tmp_project, ops)
        assert result.success
        assert (tmp_project / "src" / "auth" / "__init__.py").exists()


def test_path_traversal_rejected(tmp_project: Path) -> None:
    ops = [CreateOp(file="../etc/passwd", content="hacked")]
    result = batch_apply(tmp_project, ops)
    assert not result.success
    assert any("traversal" in (d.error or "").lower() for d in result.details)


# ---------------------------------------------------------------------------
# Merged: create-op utf-8 fidelity and batch-created-file rollback.
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


def test_create_writes_utf8(tmp_path: Path) -> None:
    """A create op writes content as utf-8, readable back identically."""
    content = "élément → 日本語\n"

    result = batch_apply(
        tmp_path,
        [CreateOp(file="created.txt", content=content)],
    )

    assert result.success, result

    created = tmp_path / "created.txt"
    assert created.read_text(encoding="utf-8") == content


def test_apply_failure_removes_batch_created_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A file created earlier in the batch is removed on rollback.

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


# ---------------------------------------------------------------------------
# Merged from tests/unit/test_engine.py (AXM-2030): CreateOp EOL fidelity --
# real-filesystem integration tests.
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_create_preserves_crlf_content(tmp_path: Path) -> None:
    """AC1: a CreateOp whose content carries CRLF is written verbatim."""
    result = batch_apply(
        tmp_path,
        [CreateOp(file="new.txt", content="red\r\ngreen\r\nblue\r\n")],
    )

    assert result.success is True
    assert (tmp_path / "new.txt").read_bytes() == b"red\r\ngreen\r\nblue\r\n"


@pytest.mark.integration
def test_create_preserves_lf_content(tmp_path: Path) -> None:
    """AC2: a CreateOp whose content carries LF is written verbatim (no CRLF leak)."""
    result = batch_apply(
        tmp_path,
        [CreateOp(file="new_lf.txt", content="red\ngreen\nblue\n")],
    )

    assert result.success is True
    assert (tmp_path / "new_lf.txt").read_bytes() == b"red\ngreen\nblue\n"


@pytest.mark.integration
def test_batch_apply_surfaces_rollback_failure(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """AC3: a partial rollback failure is surfaced on BatchResult.rollback_failed."""
    # Force the apply phase to raise so rollback runs.
    mocker.patch(
        "axm_edit.core.engine._apply_creates_deletes",
        side_effect=RuntimeError("boom"),
    )
    # Force rollback's per-path restore to fail so the rollback is partial.
    mocker.patch(
        "axm_edit.core.checkpoint._restore_one",
        side_effect=OSError("cannot restore"),
    )

    result = batch_apply(tmp_path, [CreateOp(file="new.py", content="x = 1\n")])

    assert result.success is False
    assert result.rollback_failed is True
