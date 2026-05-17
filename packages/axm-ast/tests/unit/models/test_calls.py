"""Tests for axm_ast.models.calls models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from axm_ast.models.calls import CallSite


class TestCallSiteExtraForbid:
    """CallSite rejects unknown fields."""

    def test_callsite_rejects_extra(self) -> None:
        with pytest.raises(ValidationError, match="extra_forbidden"):
            CallSite(
                module="m",
                symbol="s",
                line=1,
                column=0,
                call_expression="s()",
                bogus="x",  # type: ignore[call-arg]
            )


# ---------------------------------------------------------------------------
# CallSite model tests (merged from tests/unit/test_calls.py)
# ---------------------------------------------------------------------------


class TestCallSiteModel:
    """Tests for CallSite Pydantic model."""

    def test_create_minimal(self) -> None:
        cs = CallSite(
            module="cli",
            symbol="greet",
            line=42,
            column=8,
            call_expression='greet("world")',
        )
        assert cs.module == "cli"
        assert cs.symbol == "greet"
        assert cs.line == 42
        assert cs.column == 8
        assert cs.context is None

    def test_create_with_context(self) -> None:
        cs = CallSite(
            module="cli",
            symbol="greet",
            line=42,
            column=8,
            context="main",
            call_expression='greet("world")',
        )
        assert cs.context == "main"

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            CallSite(  # type: ignore[call-arg]
                module="cli",
                symbol="greet",
                line=42,
                column=8,
                call_expression="greet()",
                unknown_field="bad",
            )

    def test_model_dump(self) -> None:
        cs = CallSite(
            module="core",
            symbol="process",
            line=10,
            column=4,
            context="handle",
            call_expression="process(data)",
        )
        data = cs.model_dump()
        assert data["module"] == "core"
        assert data["symbol"] == "process"
        assert data["line"] == 10
        assert data["context"] == "handle"

    def test_model_dump_none_context(self) -> None:
        cs = CallSite(
            module="cli",
            symbol="fn",
            line=1,
            column=0,
            call_expression="fn()",
        )
        data = cs.model_dump()
        assert data["context"] is None
