"""Unit tests for BatchEditImportGuardTool (memory-only, no I/O).

The tool is exercised through its public ``execute`` surface. To prove the guard
never touches disk, the clean-batch case points ``path`` at a directory that
does not exist — a real filesystem read would raise, so a clean verdict is proof
of purity.
"""

from __future__ import annotations

from pytest_mock import MockerFixture

import axm_edit.import_guard_tool as guard_mod
from axm_edit.import_guard_tool import BatchEditImportGuardTool


def test_execute_on_clean_batch_returns_success_with_clean_verdict() -> None:
    """Import + consumer in the same batch → success, empty violations.

    ``path`` targets a non-existent directory: a clean run proves the guard
    reads only the op set and never the filesystem.
    """
    tool = BatchEditImportGuardTool()

    result = tool.execute(
        path="/no/such/project/dir",
        operations=[
            {
                "op": "create",
                "file": "consumer.py",
                "content": "from mod import Widget\n\nw = Widget()\n",
            },
        ],
    )

    assert result.success is True
    assert result.data["verdict"] is True
    assert result.data["violations"] == []


def test_execute_on_orphan_batch_reports_the_violation() -> None:
    """An import with no in-batch consumer surfaces file + imported_name."""
    tool = BatchEditImportGuardTool()

    result = tool.execute(
        path="/proj",
        operations=[
            {"op": "create", "file": "orphan.py", "content": "import os\n"},
        ],
    )

    assert result.success is True
    assert result.data["verdict"] is False
    violations = result.data["violations"]
    assert len(violations) == 1
    assert violations[0]["file"] == "orphan.py"
    assert violations[0]["imported_name"] == "os"
    assert "reason" in violations[0]


def test_execute_wraps_internal_failure_as_tool_result_error(
    mocker: MockerFixture,
) -> None:
    """An exception from the core is caught and returned, never raised."""
    tool = BatchEditImportGuardTool()
    mocker.patch.object(
        guard_mod,
        "detect_orphan_imports",
        side_effect=RuntimeError("boom"),
    )

    result = tool.execute(
        path="/proj",
        operations=[{"op": "create", "file": "a.py", "content": "import os\n"}],
    )

    assert result.success is False
    assert result.error is not None
    assert "boom" in result.error
