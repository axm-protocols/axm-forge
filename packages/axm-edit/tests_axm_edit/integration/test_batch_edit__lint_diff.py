"""Integration tests for the F401/F811 removal alert surfaced by batch_edit.

These drive the public :class:`BatchEditTool` end-to-end against a real project
on disk. The ruff invocation is stubbed at the ``subprocess.run`` boundary (as
in :mod:`test_batch_edit__lint`) so the *before* snapshot reports an unused
import that the *after* snapshot no longer shows — the exact shape that makes
``_run_ruff`` classify an F401 as auto-fixed. The alert must then lead the
ToolResult text, warn-only (``success`` unchanged).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from axm_edit.tools.batch_edit import BatchEditTool


@pytest.fixture(autouse=True)
def _no_global_ruff_stub() -> None:
    """Drop the global autouse stub; each test drives the gate explicitly."""
    return None


@pytest.fixture
def tool() -> BatchEditTool:
    return BatchEditTool()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "mod.py").write_text("import os\n")
    return tmp_path


def _ruff_sequence(mocker: Any, diagnostics: list[str]) -> None:
    """Stub subprocess.run so the pre-fix ruff check reports *diagnostics*.

    ``_run_ruff`` calls, in order: check (before) → --fix → format → check
    (after). Only the first check yields diagnostics; the trailing check is
    clean, so ``auto_fixed`` equals *diagnostics*.
    """
    mocker.patch("axm_edit.tools.batch_edit.ruff_available", return_value=True)
    before = mocker.Mock(returncode=1, stdout="\n".join(diagnostics))
    clean = mocker.Mock(returncode=0, stdout="")
    mocker.patch(
        "axm_edit.tools.batch_edit.subprocess.run",
        side_effect=[before, clean, clean, clean],
    )


@pytest.mark.integration
class TestBatchEditSurfacesF401Alert:
    """AC1: a batch whose autofix drops an F401 leads with the alert."""

    def test_batch_edit_surfaces_f401_alert(
        self, tool: BatchEditTool, project: Path, mocker: Any
    ) -> None:
        _ruff_sequence(mocker, ["mod.py:1:8: F401 [*] `os` imported but unused"])

        result = tool.execute(
            path=str(project),
            operations=[
                {
                    "op": "replace",
                    "file": "mod.py",
                    "edits": [
                        {"old": "import os", "new": "import os  # touched"},
                    ],
                }
            ],
        )

        assert result.success  # warn-only: success is unchanged
        text = result.text or ""
        first = text.splitlines()[0]
        assert first.startswith("⚠")
        assert "`os`" in first
        assert "mod.py" in first
        assert "F401" in first


@pytest.mark.integration
class TestCleanBatchEmitsNoAlert:
    """AC3: a batch with no dangerous removal emits no alert block."""

    def test_clean_batch_emits_no_alert(
        self, tool: BatchEditTool, project: Path, mocker: Any
    ) -> None:
        _ruff_sequence(mocker, ["mod.py:1:1: I001 [*] import block un-sorted"])

        result = tool.execute(
            path=str(project),
            operations=[
                {
                    "op": "replace",
                    "file": "mod.py",
                    "edits": [
                        {"old": "import os", "new": "import os  # touched"},
                    ],
                }
            ],
        )

        assert result.success
        text = result.text or ""
        assert "⚠ lint removed" not in text
        assert text.startswith("batch_edit | ✓")
