"""Integration tests: ``batch_apply`` behind the Python syntax gate.

Every refusal is checked on real files: nothing may be written, created or
deleted when the gate refuses a batch.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import CreateOp, Edit, ReplaceOp

pytestmark = pytest.mark.integration

DOC_MODULE = 'def f():\n    """Old doc."""\n    return 1\n'


def _snapshot(root: Path) -> dict[str, str]:
    """Map every file under *root* to the sha256 of its bytes."""
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_triple_quoted_anchor_is_replaced(tmp_path: Path) -> None:
    """A docstring line is a legitimate anchor."""
    target = tmp_path / "mod.py"
    target.write_text(DOC_MODULE, encoding="utf-8")
    ops = [
        ReplaceOp(
            file="mod.py",
            edits=[Edit(old='    """Old doc."""', new='    """New doc."""')],
        )
    ]

    result = batch_apply(tmp_path, ops)

    assert result.success, result.details
    assert target.read_text(encoding="utf-8") == DOC_MODULE.replace("Old", "New")


def test_syntax_breaking_replace_writes_nothing(tmp_path: Path) -> None:
    """An unbalanced docstring edit is refused before any write."""
    (tmp_path / "mod.py").write_text(DOC_MODULE, encoding="utf-8")
    before = _snapshot(tmp_path)
    ops = [
        ReplaceOp(
            file="mod.py",
            edits=[Edit(old='    """Old doc."""', new='    """Old doc.')],
        )
    ]

    result = batch_apply(tmp_path, ops)

    assert not result.success
    assert result.checkpoint is None
    assert result.details
    assert result.details[0].file == "mod.py"
    assert _snapshot(tmp_path) == before


def test_one_breaking_file_refuses_the_whole_batch(tmp_path: Path) -> None:
    """A valid edit on another file is not written either."""
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "mod.py").write_text(DOC_MODULE, encoding="utf-8")
    before = _snapshot(tmp_path)
    ops = [
        ReplaceOp(file="ok.py", edits=[Edit(old="x = 1", new="x = 2")]),
        ReplaceOp(file="mod.py", edits=[Edit(old="    return 1", new="    return (1")]),
        CreateOp(file="new.py", content="y = 1\n"),
    ]

    result = batch_apply(tmp_path, ops)

    assert not result.success
    assert [detail.file for detail in result.details] == ["mod.py"]
    assert _snapshot(tmp_path) == before


def test_unparseable_created_python_file_is_refused(tmp_path: Path) -> None:
    """A created ``.py`` file must parse; nothing is created otherwise."""
    result = batch_apply(tmp_path, [CreateOp(file="new.py", content="def f(:\n")])

    assert not result.success
    assert not (tmp_path / "new.py").exists()


def test_edit_on_an_already_broken_file_is_applied(tmp_path: Path) -> None:
    """The gate blocks regressions only, so a repair stays possible."""
    target = tmp_path / "mod.py"
    target.write_text("def f(:\n    return 1\n", encoding="utf-8")
    ops = [ReplaceOp(file="mod.py", edits=[Edit(old="def f(:", new="def f():")])]

    result = batch_apply(tmp_path, ops)

    assert result.success, result.details
    assert target.read_text(encoding="utf-8") == "def f():\n    return 1\n"
