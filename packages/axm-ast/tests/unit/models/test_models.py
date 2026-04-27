"""Test Pydantic models for AST node representations."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from axm_ast.models import (
    ClassInfo,
    FunctionInfo,
    FunctionKind,
    ImportInfo,
    ModuleInfo,
    PackageInfo,
    ParameterInfo,
    VariableInfo,
)

# ─── ParameterInfo ───────────────────────────────────────────────────────────


class TestParameterInfo:
    """Tests for ParameterInfo model."""

    def test_simple_param(self):
        p = ParameterInfo(name="x")
        assert p.name == "x"
        assert p.annotation is None
        assert p.default is None

    def test_annotated_param(self):
        p = ParameterInfo(name="path", annotation="Path")
        assert p.annotation == "Path"

    def test_default_param(self):
        p = ParameterInfo(name="x", default="42")
        assert p.default == "42"

    def test_full_param(self):
        p = ParameterInfo(name="x", annotation="int", default="0")
        assert p.name == "x"
        assert p.annotation == "int"
        assert p.default == "0"


# ─── FunctionInfo ────────────────────────────────────────────────────────────


class TestFunctionInfo:
    """Tests for FunctionInfo model."""

    def test_basic_function(self):
        fn = FunctionInfo(name="foo", line_start=1, line_end=3)
        assert fn.name == "foo"
        assert fn.kind == FunctionKind.FUNCTION
        assert fn.is_public is True
        assert fn.is_async is False

    def test_private_function(self):
        fn = FunctionInfo(name="_helper", line_start=1, line_end=3)
        assert fn.is_public is False

    def test_dunder_is_private(self):
        fn = FunctionInfo(name="__init__", line_start=1, line_end=3)
        assert fn.is_public is False

    def test_signature_simple(self):
        fn = FunctionInfo(name="foo", line_start=1, line_end=1)
        assert fn.signature == "def foo()"

    def test_signature_with_params(self):
        fn = FunctionInfo(
            name="add",
            params=[
                ParameterInfo(name="a", annotation="int"),
                ParameterInfo(name="b", annotation="int"),
            ],
            return_type="int",
            line_start=1,
            line_end=1,
        )
        assert fn.signature == "def add(a: int, b: int) -> int"

    def test_async_signature(self):
        fn = FunctionInfo(name="fetch", is_async=True, line_start=1, line_end=1)
        assert fn.signature == "async def fetch()"

    def test_all_kinds(self):
        for kind in FunctionKind:
            fn = FunctionInfo(name="x", kind=kind, line_start=1, line_end=1)
            assert fn.kind == kind

    def test_with_decorators(self):
        fn = FunctionInfo(
            name="x",
            decorators=["property", "cache"],
            line_start=1,
            line_end=1,
        )
        assert fn.decorators == ["property", "cache"]


# ─── ClassInfo ───────────────────────────────────────────────────────────────


class TestClassInfo:
    """Tests for ClassInfo model."""

    def test_basic_class(self):
        cls = ClassInfo(name="Foo", line_start=1, line_end=10)
        assert cls.name == "Foo"
        assert cls.is_public is True
        assert cls.bases == []
        assert cls.methods == []

    def test_private_class(self):
        cls = ClassInfo(name="_Internal", line_start=1, line_end=5)
        assert cls.is_public is False

    def test_class_with_bases(self):
        cls = ClassInfo(name="Parser", bases=["BaseModel"], line_start=1, line_end=20)
        assert cls.bases == ["BaseModel"]

    def test_class_with_methods(self):
        method = FunctionInfo(
            name="parse",
            kind=FunctionKind.METHOD,
            line_start=3,
            line_end=10,
        )
        cls = ClassInfo(name="Parser", methods=[method], line_start=1, line_end=10)
        assert len(cls.methods) == 1
        assert cls.methods[0].kind == FunctionKind.METHOD


# ─── ImportInfo ──────────────────────────────────────────────────────────────


class TestImportInfo:
    """Tests for ImportInfo model."""

    def test_absolute_import(self):
        imp = ImportInfo(module="pathlib", names=["Path"])
        assert imp.is_relative is False
        assert imp.level == 0

    def test_relative_import(self):
        imp = ImportInfo(module="utils", names=["helper"], is_relative=True, level=1)
        assert imp.is_relative is True
        assert imp.level == 1

    def test_import_with_alias(self):
        imp = ImportInfo(module="numpy", names=["numpy"], alias="np")
        assert imp.alias == "np"

    def test_star_import(self):
        imp = ImportInfo(module="os", names=["*"])
        assert "*" in imp.names


# ─── VariableInfo ────────────────────────────────────────────────────────────


class TestVariableInfo:
    """Tests for VariableInfo model."""

    def test_basic_variable(self):
        v = VariableInfo(name="MAX_SIZE", line=5)
        assert v.name == "MAX_SIZE"
        assert v.annotation is None

    def test_annotated_variable(self):
        v = VariableInfo(name="x", annotation="int", value_repr="42", line=1)
        assert v.annotation == "int"
        assert v.value_repr == "42"


# ─── ModuleInfo ──────────────────────────────────────────────────────────────


class TestModuleInfo:
    """Tests for ModuleInfo model."""

    def test_empty_module(self):
        mod = ModuleInfo(path=Path("test.py"))
        assert mod.functions == []
        assert mod.classes == []
        assert mod.all_exports is None

    def test_public_functions_no_all(self):
        """Without __all__, public = not starting with _."""
        mod = ModuleInfo(
            path=Path("test.py"),
            functions=[
                FunctionInfo(name="public", line_start=1, line_end=1),
                FunctionInfo(name="_private", line_start=2, line_end=2),
            ],
        )
        assert len(mod.public_functions) == 1
        assert mod.public_functions[0].name == "public"

    def test_public_functions_with_all(self):
        """With __all__, only listed names are public."""
        mod = ModuleInfo(
            path=Path("test.py"),
            functions=[
                FunctionInfo(name="public", line_start=1, line_end=1),
                FunctionInfo(name="_also_public", line_start=2, line_end=2),
                FunctionInfo(name="not_exported", line_start=3, line_end=3),
            ],
            all_exports=["public", "_also_public"],
        )
        assert len(mod.public_functions) == 2

    def test_public_classes(self):
        mod = ModuleInfo(
            path=Path("test.py"),
            classes=[
                ClassInfo(name="Public", line_start=1, line_end=5),
                ClassInfo(name="_Private", line_start=6, line_end=10),
            ],
        )
        assert len(mod.public_classes) == 1


# ─── PackageInfo ─────────────────────────────────────────────────────────────


class TestPackageInfo:
    """Tests for PackageInfo model."""

    def test_empty_package(self):
        pkg = PackageInfo(name="mypkg", root=Path("src/mypkg"))
        assert pkg.modules == []
        assert pkg.public_api == []
        assert pkg.module_names == []

    def test_public_api_aggregates(self):
        mod = ModuleInfo(
            path=Path("src/mypkg/core.py"),
            functions=[FunctionInfo(name="run", line_start=1, line_end=1)],
            classes=[ClassInfo(name="Engine", line_start=2, line_end=10)],
        )
        pkg = PackageInfo(name="mypkg", root=Path("src/mypkg"), modules=[mod])
        api = pkg.public_api
        assert len(api) >= 1

    def test_module_names(self):
        pkg = PackageInfo(
            name="mypkg",
            root=Path("src/mypkg"),
            modules=[
                ModuleInfo(path=Path("src/mypkg/__init__.py")),
                ModuleInfo(path=Path("src/mypkg/core.py")),
                ModuleInfo(path=Path("src/mypkg/utils/__init__.py")),
            ],
        )
        names = pkg.module_names
        assert "mypkg" in names
        assert "core" in names
        assert "utils" in names

    def test_dependency_edges(self):
        pkg = PackageInfo(
            name="mypkg",
            root=Path("src/mypkg"),
            dependency_edges=[("core", "utils"), ("cli", "core")],
        )
        assert len(pkg.dependency_edges) >= 1


# ─── Extra forbid ────────────────────────────────────────────────────────────


class TestModelExtraForbid:
    """All Pydantic models reject unknown fields."""

    def test_function_info_rejects_extra(self) -> None:
        with pytest.raises(ValidationError, match="extra_forbidden"):
            FunctionInfo(name="x", line_start=1, line_end=2, typo="bad")  # type: ignore[call-arg]

    def test_class_info_rejects_extra(self) -> None:
        with pytest.raises(ValidationError, match="extra_forbidden"):
            ClassInfo(name="X", line_start=1, line_end=2, oops=True)  # type: ignore[call-arg]

    def test_parameter_info_rejects_extra(self) -> None:
        with pytest.raises(ValidationError, match="extra_forbidden"):
            ParameterInfo(name="x", bad="field")  # type: ignore[call-arg]

    def test_module_info_rejects_extra(self) -> None:
        with pytest.raises(ValidationError, match="extra_forbidden"):
            ModuleInfo(path=Path("x.py"), nope=1)  # type: ignore[call-arg]

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

    def test_entry_point_rejects_extra(self) -> None:
        from axm_ast.core.flows import EntryPoint

        with pytest.raises(ValidationError, match="extra_forbidden"):
            EntryPoint(
                name="x",
                module="m",
                kind="test",
                line=1,
                framework="pytest",
                extra_field="bad",  # type: ignore[call-arg]
            )

    def test_flow_step_rejects_extra(self) -> None:
        from axm_ast.core.flows import FlowStep

        with pytest.raises(ValidationError, match="extra_forbidden"):
            FlowStep(
                name="x",
                module="m",
                line=1,
                depth=0,
                chain=[],
                whoops=True,  # type: ignore[call-arg]
            )
