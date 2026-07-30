"""Integration: BatchEditImportGuardTool end-to-end on a real temp project.

Exercises the tool over a real on-disk project directory and real ``batch_edit``
operation sets (clean and orphan variants), proving the guard routes through the
real ``axm-ast`` parser and leaves the project untouched (warn-only, read-only).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.import_guard_tool import BatchEditImportGuardTool


def _snapshot(root: Path) -> dict[str, str]:
    """Map every file under *root* to its text, for before/after comparison."""
    return {
        str(p.relative_to(root)): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


@pytest.mark.integration
def test_clean_op_set_yields_clean_verdict_and_leaves_project_untouched(
    tmp_path: Path,
) -> None:
    """A cross-file import + consumer op set returns a clean verdict."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "existing.py").write_text("VALUE = 1\n", encoding="utf-8")
    before = _snapshot(project)

    tool = BatchEditImportGuardTool()
    result = tool.execute(
        path=str(project),
        operations=[
            {
                "op": "create",
                "file": "provider.py",
                "content": "from helpers import compute\n",
            },
            {"op": "create", "file": "user.py", "content": "r = compute(3)\n"},
        ],
    )

    assert result.success is True
    assert result.data["verdict"] is True
    assert result.data["violations"] == []
    assert _snapshot(project) == before


@pytest.mark.integration
def test_orphan_op_set_flags_the_symbol_and_leaves_project_untouched(
    tmp_path: Path,
) -> None:
    """An orphan import op set flags exactly that file + imported symbol."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "existing.py").write_text("VALUE = 1\n", encoding="utf-8")
    before = _snapshot(project)

    tool = BatchEditImportGuardTool()
    result = tool.execute(
        path=str(project),
        operations=[
            {
                "op": "replace",
                "file": "existing.py",
                "edits": [
                    {"old": "VALUE = 1\n", "new": "import dataclasses\nVALUE = 1\n"}
                ],
            },
        ],
    )

    assert result.success is True
    assert result.data["verdict"] is False
    orphans = {(v["file"], v["imported_name"]) for v in result.data["violations"]}
    assert orphans == {("existing.py", "dataclasses")}
    assert _snapshot(project) == before
