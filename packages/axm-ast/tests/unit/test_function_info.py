"""Tests for FunctionInfo, ClassInfo, ModuleInfo, PackageInfo node models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from axm_ast.models.nodes import (
    FunctionInfo,
)


def test_signature_no_params() -> None:
    fn = FunctionInfo(name="run", line_start=1, line_end=1)
    assert fn.signature == "def run()"


def test_signature_async() -> None:
    fn = FunctionInfo(
        name="fetch",
        return_type="bytes",
        is_async=True,
        line_start=1,
        line_end=5,
    )
    assert fn.signature is not None
    assert fn.signature.startswith("async def fetch")


def test_extra_fields_forbidden() -> None:
    with pytest.raises(Exception):  # noqa: B017
        FunctionInfo(  # type: ignore[call-arg]
            name="fn", line_start=1, line_end=1, unknown="bad"
        )


def test_dunder_is_private():
    fn = FunctionInfo(name="__init__", line_start=1, line_end=3)
    assert fn.is_public is False


def test_with_decorators():
    fn = FunctionInfo(
        name="x",
        decorators=["property", "cache"],
        line_start=1,
        line_end=1,
    )
    assert fn.decorators == ["property", "cache"]


def test_function_info_rejects_extra() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        FunctionInfo(name="x", line_start=1, line_end=2, typo="bad")  # type: ignore[call-arg]
