from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from axm_ast.models import ClassInfo, FunctionInfo, ParamInfo, VariableInfo
from axm_ast.tools.inspect_detail import (
    build_detail,
    build_module_detail,
    class_detail,
    function_detail,
    variable_detail,
)

# ---------------------------------------------------------------------------
# Fixtures — model-based samples
# ---------------------------------------------------------------------------


@pytest.fixture
def _sample_function() -> FunctionInfo:
    return FunctionInfo(
        name="my_func",
        line_start=10,
        line_end=20,
        signature="(x: int, y: str) -> bool",
        params=[
            ParamInfo(name="x", annotation="int", default=None),
            ParamInfo(name="y", annotation="str", default="'hello'"),
        ],
        return_type="bool",
        docstring="A function.",
    )


@pytest.fixture
def _sample_class() -> ClassInfo:
    method = FunctionInfo(
        name="run",
        line_start=15,
        line_end=18,
        signature="(self) -> None",
        params=[],
        return_type="None",
        docstring=None,
    )
    return ClassInfo(
        name="Runner",
        line_start=10,
        line_end=25,
        docstring="Runner class.",
        bases=["BaseRunner"],
        methods=[method],
    )


@pytest.fixture
def _sample_variable() -> VariableInfo:
    return VariableInfo(
        name="MAX_SIZE",
        line=5,
        annotation="int",
        value_repr="100",
    )


# ---------------------------------------------------------------------------
# Fixtures — SimpleNamespace samples (used by kind tests)
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_fn_ns() -> Any:
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
def sample_cls_ns() -> Any:
    return SimpleNamespace(
        name="MyCls",
        line_start=30,
        line_end=50,
        docstring="A class.",
        bases=["Base"],
        methods=[],
    )


@pytest.fixture
def sample_var_ns() -> Any:
    return SimpleNamespace(
        name="my_var",
        line=5,
        annotation="int",
        value_repr="42",
    )


@pytest.fixture
def sample_module_ns() -> tuple[Any, Any]:
    pkg = SimpleNamespace(path="/project")
    mod = SimpleNamespace(
        path="/project/src/mod.py",
        docstring="A module.",
        functions=[],
        classes=[],
    )
    return pkg, mod


# ---------------------------------------------------------------------------
# Fixtures — model-based samples for the "no module" tests
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_var_no_module() -> VariableInfo:
    return VariableInfo(name="MAX_RETRIES", line=10, annotation="int", value_repr="3")


@pytest.fixture
def sample_fn_no_module() -> FunctionInfo:
    return FunctionInfo(
        name="run",
        line_start=5,
        line_end=15,
        signature="(self, timeout: int = 30) -> None",
        params=[],
    )


@pytest.fixture
def sample_cls_no_module() -> ClassInfo:
    return ClassInfo(
        name="Runner",
        line_start=1,
        line_end=50,
        bases=["Base"],
        methods=[],
    )


@pytest.fixture()
def var_info() -> VariableInfo:
    return VariableInfo(name="MY_VAR", line=5, annotation="int", value_repr="42")


# ---------------------------------------------------------------------------
# Unit tests — build_detail core behavior
# ---------------------------------------------------------------------------


class TestBuildDetail:
    """Verify detail building produces same output after extraction."""

    def test_function_detail_keys(self, _sample_function: FunctionInfo) -> None:
        detail = build_detail(_sample_function, file="pkg/mod.py")
        assert detail["name"] == "my_func"
        assert detail["file"] == "pkg/mod.py"
        assert detail["start_line"] == 10
        assert detail["end_line"] == 20
        assert detail["signature"] == "(x: int, y: str) -> bool"
        assert detail["return_type"] == "bool"
        assert detail["docstring"] == "A function."
        assert len(detail["parameters"]) == 2
        assert detail["parameters"][1]["default"] == "'hello'"

    def test_class_detail_keys(self, _sample_class: ClassInfo) -> None:
        detail = build_detail(_sample_class, file="pkg/runner.py")
        assert detail["name"] == "Runner"
        assert detail["bases"] == ["BaseRunner"]
        assert detail["methods"] == ["run"]
        assert detail["start_line"] == 10
        assert detail["end_line"] == 25

    def test_variable_detail_keys(self, _sample_variable: VariableInfo) -> None:
        detail = build_detail(_sample_variable, file="pkg/const.py")
        assert detail["name"] == "MAX_SIZE"
        assert detail["kind"] == "variable"
        assert detail["annotation"] == "int"
        assert detail["value_repr"] == "100"

    def test_source_not_included_by_default(
        self, _sample_function: FunctionInfo
    ) -> None:
        detail = build_detail(_sample_function, file="mod.py")
        assert "source" not in detail

    def test_build_module_detail(self) -> None:
        from unittest.mock import MagicMock

        from axm_ast.models import ClassInfo, FunctionInfo, ModuleInfo, PackageInfo

        mod = ModuleInfo(
            path=Path("/fake/src/mypkg/core.py"),
            name="core",
            docstring="core module",
            functions=[FunctionInfo(name="fn1", line_start=1, line_end=2)],
            classes=[ClassInfo(name="Cls1", line_start=4, line_end=10)],
            variables=[],
            imports=[],
        )
        pkg = MagicMock(spec=PackageInfo)
        pkg.root = Path("/fake/src/mypkg")

        detail = build_module_detail(pkg, mod, "core")
        assert detail["kind"] == "module"
        assert detail["name"] == "core"
        assert detail["functions"] == ["fn1"]
        assert detail["classes"] == ["Cls1"]
        assert detail["symbol_count"] == 2


# ---------------------------------------------------------------------------
# Unit tests — "kind" key emitted by every detail builder
# ---------------------------------------------------------------------------


def test_function_detail_has_kind(sample_fn_ns: Any) -> None:
    detail = function_detail(sample_fn_ns, file="mod.py")
    assert detail["kind"] == "function"


def test_class_detail_has_kind(sample_cls_ns: Any) -> None:
    detail = class_detail(sample_cls_ns, file="mod.py")
    assert detail["kind"] == "class"


def test_all_detail_builders_emit_kind(
    sample_fn_ns: Any,
    sample_cls_ns: Any,
    sample_var_ns: Any,
    sample_module_ns: tuple[Any, Any],
) -> None:
    pkg, mod = sample_module_ns
    results: list[tuple[str, dict[str, Any]]] = [
        ("function", function_detail(sample_fn_ns, file="f.py")),
        ("class", class_detail(sample_cls_ns, file="f.py")),
        ("variable", variable_detail(sample_var_ns, file="f.py")),
        ("module", build_module_detail(pkg, mod, "my_mod")),
    ]
    for expected_kind, detail in results:
        assert "kind" in detail, f"missing kind for {expected_kind}"
        assert detail["kind"] == expected_kind


# ---------------------------------------------------------------------------
# Unit tests — no spurious 'module' key in non-module details
# ---------------------------------------------------------------------------


def test_variable_detail_no_module_key(sample_var_no_module: VariableInfo) -> None:
    result = variable_detail(sample_var_no_module, file="pkg/const.py")
    assert "module" not in result


def test_function_detail_no_module_key(sample_fn_no_module: FunctionInfo) -> None:
    result = function_detail(sample_fn_no_module, file="pkg/mod.py")
    assert "module" not in result


def test_class_detail_no_module_key(sample_cls_no_module: ClassInfo) -> None:
    result = class_detail(sample_cls_no_module, file="pkg/runner.py")
    assert "module" not in result


def test_build_detail_no_module_key_for_any_symbol(
    sample_var_no_module: VariableInfo,
    sample_fn_no_module: FunctionInfo,
    sample_cls_no_module: ClassInfo,
) -> None:
    """Simulates batch inspect — none of the returned dicts should contain 'module'."""
    symbols: list[tuple[VariableInfo | FunctionInfo | ClassInfo, str]] = [
        (sample_var_no_module, "pkg/const.py"),
        (sample_fn_no_module, "pkg/mod.py"),
        (sample_cls_no_module, "pkg/runner.py"),
    ]
    for sym, file in symbols:
        detail = build_detail(sym, file=file)
        assert "module" not in detail, f"'module' found in detail for {sym.name}"


# ---------------------------------------------------------------------------
# Unit tests — variable source handling (source=True / abs_path)
# ---------------------------------------------------------------------------


class TestVariableSourceIncluded:
    """AC1: build_detail(variable, source=True, abs_path=...) includes source key."""

    def test_variable_source_included(self, var_info: VariableInfo) -> None:
        with patch(
            "axm_ast.tools.inspect_detail.read_source", return_value="MY_VAR: int = 42"
        ) as mock_rs:
            detail = build_detail(
                var_info, file="f.py", abs_path="/tmp/f.py", source=True
            )

        assert "source" in detail
        assert detail["source"] == "MY_VAR: int = 42"
        mock_rs.assert_called_once_with("/tmp/f.py", 5, 5)


class TestVariableSourceNotIncluded:
    """AC2: build_detail(variable, source=False) does NOT include source key."""

    def test_variable_source_not_included_by_default(
        self, var_info: VariableInfo
    ) -> None:
        detail = build_detail(var_info, file="f.py")

        assert "source" not in detail


class TestVariableSourceEdgeCases:
    """Edge cases for variable source handling."""

    def test_variable_source_true_no_abs_path(self, var_info: VariableInfo) -> None:
        """source=True but abs_path is empty -> no source key."""
        detail = build_detail(var_info, file="f.py", abs_path="", source=True)

        assert "source" not in detail
