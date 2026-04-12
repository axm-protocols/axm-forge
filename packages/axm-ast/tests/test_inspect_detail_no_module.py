from __future__ import annotations

import pytest

from axm_ast.models import ClassInfo, FunctionInfo, VariableInfo
from axm_ast.tools.inspect_detail import (
    build_detail,
    class_detail,
    function_detail,
    variable_detail,
)


@pytest.fixture
def sample_var() -> VariableInfo:
    return VariableInfo(name="MAX_RETRIES", line=10, annotation="int", value_repr="3")


@pytest.fixture
def sample_fn() -> FunctionInfo:
    return FunctionInfo(
        name="run",
        line_start=5,
        line_end=15,
        signature="(self, timeout: int = 30) -> None",
        params=[],
    )


@pytest.fixture
def sample_cls() -> ClassInfo:
    return ClassInfo(
        name="Runner",
        line_start=1,
        line_end=50,
        bases=["Base"],
        methods=[],
    )


# --- Unit tests ---


def test_variable_detail_no_module_key(sample_var: VariableInfo) -> None:
    result = variable_detail(sample_var, file="pkg/const.py")
    assert "module" not in result


def test_function_detail_no_module_key(sample_fn: FunctionInfo) -> None:
    result = function_detail(sample_fn, file="pkg/mod.py")
    assert "module" not in result


def test_class_detail_no_module_key(sample_cls: ClassInfo) -> None:
    result = class_detail(sample_cls, file="pkg/runner.py")
    assert "module" not in result


# --- Edge case: build_detail (batch inspect entry point) ---


def test_build_detail_no_module_key_for_any_symbol(
    sample_var: VariableInfo,
    sample_fn: FunctionInfo,
    sample_cls: ClassInfo,
) -> None:
    """Simulates batch inspect — none of the returned dicts should contain 'module'."""
    symbols: list[tuple[VariableInfo | FunctionInfo | ClassInfo, str]] = [
        (sample_var, "pkg/const.py"),
        (sample_fn, "pkg/mod.py"),
        (sample_cls, "pkg/runner.py"),
    ]
    for sym, file in symbols:
        detail = build_detail(sym, file=file)
        assert "module" not in detail, f"'module' found in detail for {sym.name}"
