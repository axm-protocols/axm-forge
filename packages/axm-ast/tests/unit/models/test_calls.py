"""Tests for axm_ast.models.calls models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestCallSiteExtraForbid:
    """CallSite rejects unknown fields."""

    def test_callsite_rejects_extra(self) -> None:
        from axm_ast.models.calls import CallSite

        with pytest.raises(ValidationError, match="extra_forbidden"):
            CallSite(
                module="m",
                symbol="s",
                line=1,
                column=0,
                call_expression="s()",
                bogus="x",  # type: ignore[call-arg]
            )
