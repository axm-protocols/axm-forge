"""Integration tests for AuditFixTool — real pipeline behaviour with mocked run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from axm_audit.core.fix.models import FileOp, PipelineReport
from axm_audit.tools.audit_fix import AuditFixTool

pytestmark = pytest.mark.integration


def test_execute_data_is_json_serializable(tmp_path: Path, mocker: Any) -> None:
    """AC8: synthetic PipelineReport with Path + list[Path] → json.dumps OK."""
    split_op = FileOp(
        kind="split",
        source=tmp_path / "tests" / "unit" / "test_a.py",
        target=[
            tmp_path / "tests" / "unit" / "test_x.py",
            tmp_path / "tests" / "unit" / "test_y.py",
        ],
        rationale="split for AC8",
        source_rule="TEST_QUALITY_FILE_NAMING",
        split_map={"test_x.py": ["test_x"], "test_y.py": ["test_y"]},
    )
    relocate_op = FileOp(
        kind="relocate",
        source=tmp_path / "tests" / "unit" / "test_b.py",
        target=tmp_path / "tests" / "integration" / "test_b.py",
        rationale="relocate for AC8",
        source_rule="TEST_PYRAMID",
    )
    report = PipelineReport(
        ops=[split_op, relocate_op],
        unfixable=[{"rule_id": "X", "test_file": "tests/unit/test_z.py"}],
        applied=False,
        warnings=["some warning"],
        iterations=1,
    )
    mocker.patch("axm_audit.core.fix.run", return_value=report)

    result = AuditFixTool().execute(path=str(tmp_path))

    assert result.success is True
    assert result.data is not None
    json.dumps(result.data)  # must not raise
    assert isinstance(result.data["ops"], list)
    assert len(result.data["ops"]) == 2
    for op_dict in result.data["ops"]:
        assert isinstance(op_dict["source"], str)
        assert not isinstance(op_dict["source"], Path)
        tgt = op_dict["target"]
        if isinstance(tgt, list):
            for t in tgt:
                assert isinstance(t, str)
        else:
            assert isinstance(tgt, str)
