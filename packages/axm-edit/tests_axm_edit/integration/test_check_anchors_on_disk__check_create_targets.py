"""Integration tests for the filesystem-resolving precheck layer.

Real files under ``tmp_path``; the checks are strictly read-only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.core.precheck import CheckDiagnostic
from axm_edit.core.precheck_fs import (
    check_anchors_on_disk,
    check_create_targets,
    run_fs_checks,
)
from axm_edit.models.operations import CreateOp, Edit, ReplaceOp


def _snapshot(root: Path) -> dict[str, float]:
    """Map every file under *root* to its mtime."""
    return {
        str(p.relative_to(root)): p.stat().st_mtime
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


@pytest.mark.integration
def test_create_on_existing_path_is_reported(tmp_path: Path) -> None:
    """AC1: a create targeting an existing file is an error with a hint."""
    (tmp_path / "a.py").write_text("x = 1\n")
    operations = [CreateOp(file="a.py", content="x = 2\n")]

    diagnostics = check_create_targets(tmp_path, operations)

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "CREATE_ON_EXISTING"
    assert diagnostics[0].severity == "error"
    assert "atomic" in diagnostics[0].hint.lower()


@pytest.mark.integration
def test_create_on_free_path_is_silent(tmp_path: Path) -> None:
    """AC1: a create on a free path yields no diagnostic."""
    operations = [CreateOp(file="neuf.py", content="x = 1\n")]

    assert check_create_targets(tmp_path, operations) == []


@pytest.mark.integration
def test_missing_anchor_on_disk_is_reported(tmp_path: Path) -> None:
    """AC2: an anchor absent from the file on disk is ANCHOR_NOT_FOUND."""
    (tmp_path / "a.py").write_text("x = 1\n")
    operations = [ReplaceOp(file="a.py", edits=[Edit(old="y = 2", new="y = 3")])]

    diagnostics = check_anchors_on_disk(tmp_path, operations)

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "ANCHOR_NOT_FOUND"
    assert diagnostics[0].severity == "error"


@pytest.mark.integration
def test_duplicated_anchor_is_a_warning(tmp_path: Path) -> None:
    """AC3: an anchor found twice is ANCHOR_AMBIGUOUS, severity warning."""
    (tmp_path / "a.py").write_text("x = 1\nx = 1\n")
    operations = [ReplaceOp(file="a.py", edits=[Edit(old="x = 1", new="x = 2")])]

    diagnostics = check_anchors_on_disk(tmp_path, operations)

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "ANCHOR_AMBIGUOUS"
    assert diagnostics[0].severity == "warning"


@pytest.mark.integration
def test_unique_anchor_yields_no_diagnostic(tmp_path: Path) -> None:
    """AC3: an anchor appearing exactly once yields no diagnostic."""
    (tmp_path / "a.py").write_text("x = 1\ny = 2\n")
    operations = [ReplaceOp(file="a.py", edits=[Edit(old="y = 2", new="y = 3")])]

    assert check_anchors_on_disk(tmp_path, operations) == []


@pytest.mark.integration
def test_run_fs_checks_reads_without_mutating(tmp_path: Path) -> None:
    """AC7: the aggregate reads the tree and never creates/edits/deletes."""
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.py").write_text("y = 2\n")
    operations = [
        CreateOp(file="a.py", content="x = 9\n"),
        ReplaceOp(file="b.py", edits=[Edit(old="y = 2", new="y = 3")]),
        {"op": "delete", "file": "b.py"},
    ]
    before = _snapshot(tmp_path)

    diagnostics = run_fs_checks(tmp_path, operations)

    assert _snapshot(tmp_path) == before
    assert isinstance(diagnostics, list)
    assert all(isinstance(d, CheckDiagnostic) for d in diagnostics)


@pytest.mark.integration
def test_on_disk_anchor_diagnostics_carry_their_edit_slot(tmp_path: Path) -> None:
    """AC7: not-found and ambiguous anchors name their edit slot and excerpt."""
    (tmp_path / "a.py").write_text("flag = 1\nflag = 1\n")
    operations = [
        ReplaceOp(
            file="a.py",
            edits=[
                Edit(old="absent = 0", new="absent = 1"),
                Edit(old="flag = 1", new="flag = 2"),
            ],
        )
    ]

    diagnostics = check_anchors_on_disk(tmp_path, operations)

    by_code = {item.code: item for item in diagnostics}
    assert set(by_code) == {"ANCHOR_NOT_FOUND", "ANCHOR_AMBIGUOUS"}
    assert by_code["ANCHOR_NOT_FOUND"].edit_index == 0
    assert by_code["ANCHOR_AMBIGUOUS"].edit_index == 1
    assert by_code["ANCHOR_NOT_FOUND"].anchor_excerpt
    assert by_code["ANCHOR_AMBIGUOUS"].anchor_excerpt
