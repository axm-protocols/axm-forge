from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from axm_ast.tools.inspect_detail import (
    build_module_detail,
    class_detail,
    function_detail,
    variable_detail,
)


@pytest.fixture
def sample_fn() -> Any:
    return SimpleNamespace(
        name="my_func",
        line_start=10,
        line_end=20,
        docstring="A function.",
        signature="(x: int) -> str",
        return_type="str",
        params=[],
    )


@pytest.fixture
def sample_cls() -> Any:
    return SimpleNamespace(
        name="MyCls",
        line_start=30,
        line_end=50,
        docstring="A class.",
        bases=["Base"],
        methods=[],
    )


@pytest.fixture
def sample_var() -> Any:
    return SimpleNamespace(
        name="my_var",
        line=5,
        annotation="int",
        value_repr="42",
    )


@pytest.fixture
def sample_module() -> tuple[Any, Any]:
    pkg = SimpleNamespace(path="/project")
    mod = SimpleNamespace(
        path="/project/src/mod.py",
        docstring="A module.",
        functions=[],
        classes=[],
    )
    return pkg, mod


# --- Unit tests ---


def test_function_detail_has_kind(sample_fn: Any) -> None:
    detail = function_detail(sample_fn, file="mod.py")
    assert detail["kind"] == "function"


def test_class_detail_has_kind(sample_cls: Any) -> None:
    detail = class_detail(sample_cls, file="mod.py")
    assert detail["kind"] == "class"


# --- Edge case: consistency across all 4 detail builders ---


def test_all_detail_builders_emit_kind(
    sample_fn: Any,
    sample_cls: Any,
    sample_var: Any,
    sample_module: tuple[Any, Any],
) -> None:
    pkg, mod = sample_module
    results: list[tuple[str, dict[str, Any]]] = [
        ("function", function_detail(sample_fn, file="f.py")),
        ("class", class_detail(sample_cls, file="f.py")),
        ("variable", variable_detail(sample_var, file="f.py")),
        ("module", build_module_detail(pkg, mod, "my_mod")),
    ]
    for expected_kind, detail in results:
        assert "kind" in detail, f"missing kind for {expected_kind}"
        assert detail["kind"] == expected_kind
