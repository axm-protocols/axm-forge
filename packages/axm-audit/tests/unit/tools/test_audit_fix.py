"""Unit tests for AuditFixTool MCP tool (AXM-1750).

In-memory only. The pipeline ``run`` is mocked so this module does not
touch the filesystem beyond the pytest-managed ``tmp_path``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from axm_audit.core.fix.models import FileOp, PipelineReport
from axm_audit.tools.audit_fix import AuditFixTool


class TestAuditFixToolName:
    """AC1: tool exposes the ``audit_fix`` registry name."""

    def test_name_property_returns_audit_fix(self) -> None:
        """AC1: AuditFixTool().name == 'audit_fix'."""
        assert AuditFixTool().name == "audit_fix"


class TestAuditFixToolInvalidPath:
    """AC4: bad path returns an error ToolResult, never raises."""

    def test_execute_invalid_path_returns_error_result(self) -> None:
        """AC4: execute on a non-existent path returns success=False."""
        result = AuditFixTool().execute(path="/nonexistent/path/xyz-axm-1750")

        assert result.success is False
        assert result.error is not None
        assert "Not a directory" in result.error


class TestAuditFixToolCatchesInternalException:
    """AC6: internal exceptions are caught and surfaced as error results."""

    def test_execute_catches_internal_exception(
        self, tmp_path: Path, mocker: Any
    ) -> None:
        """AC6: a RuntimeError from the pipeline becomes ToolResult.error."""
        mocker.patch(
            "axm_audit.core.fix.run",
            side_effect=RuntimeError("boom"),
        )

        result = AuditFixTool().execute(path=str(tmp_path))

        assert result.success is False
        assert result.error == "boom"


class TestAuditFixToolJsonSerializable:
    """AC8: ToolResult.data is JSON-serializable.

    Escalated from the test_spec's direct ``_report_to_dict`` import:
    the conversion is exercised through the public ``execute`` boundary
    instead of the private helper.
    """

    def test_execute_data_is_json_serializable(
        self, tmp_path: Path, mocker: Any
    ) -> None:
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
