from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.models import ClassInfo, FunctionInfo, ParamInfo, VariableInfo


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


class TestBuildDetail:
    """Verify detail building produces same output after extraction."""

    def test_function_detail_keys(self, _sample_function: FunctionInfo) -> None:
        from axm_ast.tools.inspect_detail import build_detail

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
        from axm_ast.tools.inspect_detail import build_detail

        detail = build_detail(_sample_class, file="pkg/runner.py")
        assert detail["name"] == "Runner"
        assert detail["bases"] == ["BaseRunner"]
        assert detail["methods"] == ["run"]
        assert detail["start_line"] == 10
        assert detail["end_line"] == 25

    def test_variable_detail_keys(self, _sample_variable: VariableInfo) -> None:
        from axm_ast.tools.inspect_detail import build_detail

        detail = build_detail(_sample_variable, file="pkg/const.py")
        assert detail["name"] == "MAX_SIZE"
        assert detail["kind"] == "variable"
        assert detail["annotation"] == "int"
        assert detail["value_repr"] == "100"

    def test_source_included_when_requested(
        self, _sample_function: FunctionInfo, tmp_path: Path
    ) -> None:
        from axm_ast.tools.inspect_detail import build_detail

        src_file = tmp_path / "mod.py"
        lines = [f"line {i}" for i in range(1, 25)]
        src_file.write_text("\n".join(lines))
        detail = build_detail(
            _sample_function,
            file="mod.py",
            abs_path=str(src_file),
            source=True,
        )
        assert "source" in detail
        assert "line 10" in detail["source"]

    def test_source_not_included_by_default(
        self, _sample_function: FunctionInfo
    ) -> None:
        from axm_ast.tools.inspect_detail import build_detail

        detail = build_detail(_sample_function, file="mod.py")
        assert "source" not in detail

    def test_build_module_detail(self) -> None:
        from pathlib import Path
        from unittest.mock import MagicMock

        from axm_ast.models import ModuleInfo, PackageInfo
        from axm_ast.tools.inspect_detail import build_module_detail

        mod = ModuleInfo(
            path=Path("/fake/src/mypkg/core.py"),
            name="core",
            docstring="core module",
            functions=[MagicMock(name="fn1", spec=["name"])],
            classes=[MagicMock(name="Cls1", spec=["name"])],
            variables=[],
            imports=[],
        )
        mod.functions[0].name = "fn1"
        mod.classes[0].name = "Cls1"
        pkg = MagicMock(spec=PackageInfo)
        pkg.root = Path("/fake/src/mypkg")

        detail = build_module_detail(pkg, mod, "core")
        assert detail["kind"] == "module"
        assert detail["name"] == "core"
        assert detail["functions"] == ["fn1"]
        assert detail["classes"] == ["Cls1"]
        assert detail["symbol_count"] == 2
