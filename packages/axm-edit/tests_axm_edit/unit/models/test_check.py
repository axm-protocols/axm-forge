"""Unit tests for axm_edit.models.check — the structured diagnostic model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from axm_edit.models.check import CheckDiagnostic


class TestCheckDiagnostic:
    """AC1: CheckDiagnostic exposes exactly the six contract fields."""

    def test_model_dump_exposes_exactly_the_six_contract_fields(self) -> None:
        """AC1: model_dump() returns exactly the six declared keys and values."""
        diagnostic = CheckDiagnostic(
            op_index=0,
            file="a.py",
            severity="error",
            code="X",
            message="m",
            hint="h",
        )

        dumped = diagnostic.model_dump()

        assert set(dumped) == {
            "op_index",
            "file",
            "severity",
            "code",
            "message",
            "hint",
        }
        assert dumped == {
            "op_index": 0,
            "file": "a.py",
            "severity": "error",
            "code": "X",
            "message": "m",
            "hint": "h",
        }

    def test_severity_outside_the_literal_is_rejected(self) -> None:
        """AC1: severity is a closed Literal[\"error\", \"warning\"]."""
        with pytest.raises(ValidationError):
            CheckDiagnostic(
                op_index=0,
                file="a.py",
                severity="fatal",
                code="X",
                message="m",
                hint="h",
            )
