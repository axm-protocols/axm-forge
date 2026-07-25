"""Integration test: orphan-import detection over a real multi-file op set.

Exercises the detector end-to-end on a real on-disk project directory and a
multi-file ``batch_edit`` operation set, proving that import extraction and
name-usage detection route through the real ``axm-ast`` tree-sitter parser
(AC5) without parser errors.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.import_guard import detect_orphan_imports


@pytest.mark.integration
def test_detector_reuses_axm_ast_primitives_on_real_multi_file_op_set(
    tmp_path: Path,
) -> None:
    """A two-file op set: one orphan import, one import consumed cross-file."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "existing.py").write_text("VALUE = 1\n", encoding="utf-8")

    operation_set = {
        "path": str(project),
        "operations": [
            {
                "op": "create",
                "file": "provider.py",
                "content": "from helpers import compute\n",
            },
            {
                "op": "create",
                "file": "user.py",
                "content": "result = compute(3)\n",
            },
            {
                "op": "replace",
                "file": "existing.py",
                "edits": [
                    {
                        "old": "VALUE = 1\n",
                        "new": "import dataclasses\nVALUE = 1\n",
                    }
                ],
            },
        ],
    }

    report = detect_orphan_imports(operation_set)

    # `compute` is imported in provider.py and consumed in user.py -> clean.
    # `dataclasses` is imported in existing.py with no consumer -> orphan.
    assert report.verdict is False
    orphans = {(v.file, v.imported_name) for v in report.violations}
    assert orphans == {("existing.py", "dataclasses")}
