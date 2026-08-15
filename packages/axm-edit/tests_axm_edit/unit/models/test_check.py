"""Unit tests for axm_edit.models.check — the structured diagnostic model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from axm_edit.models.check import CheckDiagnostic


class TestCheckDiagnostic:
    """AC1: CheckDiagnostic exposes exactly the six contract fields."""

    def test_model_dump_exposes_the_full_diagnostic_contract(self) -> None:
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
            "edit_index",
            "anchor_excerpt",
        }
        assert dumped == {
            "op_index": 0,
            "file": "a.py",
            "severity": "error",
            "code": "X",
            "message": "m",
            "hint": "h",
            "edit_index": None,
            "anchor_excerpt": None,
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

    def test_legacy_construction_defaults_the_two_new_fields_to_none(self) -> None:
        """AC1: the four-argument construction still works, both fields None."""
        diagnostic = CheckDiagnostic(
            op_index=0,
            file="a.py",
            code="X",
            message="m",
        )

        assert diagnostic.edit_index is None
        assert diagnostic.anchor_excerpt is None

    def test_edit_index_and_anchor_excerpt_round_trip(self) -> None:
        """AC1: both new optional fields survive model_dump()."""
        diagnostic = CheckDiagnostic(
            op_index=0,
            file="a.py",
            code="X",
            message="m",
            edit_index=1,
            anchor_excerpt="x = 1",
        )

        dumped = diagnostic.model_dump()

        assert dumped["edit_index"] == 1
        assert dumped["anchor_excerpt"] == "x = 1"
