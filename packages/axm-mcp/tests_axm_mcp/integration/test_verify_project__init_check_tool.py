"""Preserve the real governance schema across the verify boundary."""

from functools import partial
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest
from axm import AXMTool
from axm_init import quality_trace
from axm_init.tools.check import InitCheckTool

from axm_mcp import verify_project

pytestmark = pytest.mark.integration


def test_real_governance_refusal_preserves_score_and_receipt(
    tmp_path: Path, monkeypatch
):
    history = tmp_path / "history"
    monkeypatch.setattr(quality_trace, "_quality_dir", lambda: history)
    exported = tmp_path / "export"
    exported.mkdir()
    origin = {
        "path": str(tmp_path.resolve() / "source" / "demo"),
        "sha": "a" * 40,
        "branch": "dev",
    }
    checker = InitCheckTool()
    with patch.object(
        checker, "execute", wraps=partial(checker.execute, category="structure")
    ):
        result = verify_project(
            str(exported), {"init_check": cast(AXMTool, checker)}, origin=origin
        )
    governance = result["governance"]
    assert isinstance(governance, dict)
    assert governance["score"] < 100
    assert governance["failures"]
    assert governance["snapshot_recorded"] is True
    assert (history / "demo.jsonl").is_file()
