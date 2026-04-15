"""Tests for FunctionInfo, ClassInfo, ModuleInfo, PackageInfo node models."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    FunctionKind,
    ImportInfo,
    ModuleInfo,
    PackageInfo,
    ParameterInfo,
    VariableInfo,
    WorkspaceInfo,
)

# ─── ParameterInfo ──────────────────────────────────────────────────────────


class TestParameterInfo:
    """Tests for ParameterInfo model."""

    def test_create_minimal(self) -> None:
        p = ParameterInfo(name="x")
        assert p.name == "x"
        assert p.annotation is None
        assert p.default is None

    def test_create_fully_typed(self) -> None:
        p = ParameterInfo(name="path", annotation="Path", default="None")
        assert p.annotation == "Path"
        assert p.default == "None"


# ─── FunctionKind ────────────────────────────────────────────────────────────


class TestFunctionKind:
    """Tests for FunctionKind enum."""

    def test_all_values(self) -> None:
        actual = {k.value for k in FunctionKind}
        required = {"function", "method", "property", "classmethod", "staticmethod"}
        assert required.issubset(actual)

    def test_str_enum(self) -> None:
        assert str(FunctionKind.FUNCTION) == "function"
        assert FunctionKind("method") == FunctionKind.METHOD


# ─── FunctionInfo ────────────────────────────────────────────────────────────


class TestFunctionInfo:
    """Tests for FunctionInfo model."""

    def test_is_public(self) -> None:
        fn = FunctionInfo(name="greet", line_start=1, line_end=5)
        assert fn.is_public is True

    def test_is_private(self) -> None:
        fn = FunctionInfo(name="_helper", line_start=1, line_end=5)
        assert fn.is_public is False

    def test_signature_no_params(self) -> None:
        fn = FunctionInfo(name="run", line_start=1, line_end=1)
        assert fn.signature == "def run()"

    def test_signature_with_params(self) -> None:
        fn = FunctionInfo(
            name="greet",
            params=[ParameterInfo(name="name", annotation="str")],
            return_type="str",
            line_start=1,
            line_end=3,
        )
        assert fn.signature == "def greet(name: str) -> str"

    def test_signature_async(self) -> None:
        fn = FunctionInfo(
            name="fetch",
            return_type="bytes",
            is_async=True,
            line_start=1,
            line_end=5,
        )
        assert fn.signature is not None
        assert fn.signature.startswith("async def fetch")

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            FunctionInfo(  # type: ignore[call-arg]
                name="fn", line_start=1, line_end=1, unknown="bad"
            )


# ─── ClassInfo ───────────────────────────────────────────────────────────────


class TestClassInfo:
    """Tests for ClassInfo model."""

    def test_is_public(self) -> None:
        cls = ClassInfo(name="Parser", line_start=1, line_end=50)
        assert cls.is_public is True

    def test_is_private(self) -> None:
        cls = ClassInfo(name="_Internal", line_start=1, line_end=10)
        assert cls.is_public is False

    def test_with_bases(self) -> None:
        cls = ClassInfo(
            name="MyModel",
            bases=["BaseModel"],
            line_start=1,
            line_end=20,
        )
        assert "BaseModel" in cls.bases


# ─── ImportInfo ──────────────────────────────────────────────────────────────


class TestImportInfo:
    """Tests for ImportInfo model."""

    def test_absolute_import(self) -> None:
        imp = ImportInfo(module="pathlib", names=["Path"])
        assert imp.is_relative is False
        assert imp.level == 0

    def test_relative_import(self) -> None:
        imp = ImportInfo(module="utils", names=["helper"], is_relative=True, level=1)
        assert imp.is_relative is True
        assert imp.level == 1


# ─── VariableInfo ────────────────────────────────────────────────────────────


class TestVariableInfo:
    """Tests for VariableInfo model."""

    def test_create(self) -> None:
        v = VariableInfo(name="__all__", line=5)
        assert v.name == "__all__"
        assert v.annotation is None


# ─── ModuleInfo ──────────────────────────────────────────────────────────────


class TestModuleInfo:
    """Tests for ModuleInfo model."""

    def test_public_functions_with_all(self) -> None:
        mod = ModuleInfo(
            path=Path("test.py"),
            functions=[
                FunctionInfo(name="public_fn", line_start=1, line_end=5),
                FunctionInfo(name="_private_fn", line_start=6, line_end=10),
            ],
            all_exports=["public_fn"],
        )
        assert len(mod.public_functions) == 1
        assert mod.public_functions[0].name == "public_fn"

    def test_public_functions_without_all(self) -> None:
        mod = ModuleInfo(
            path=Path("test.py"),
            functions=[
                FunctionInfo(name="public_fn", line_start=1, line_end=5),
                FunctionInfo(name="_private_fn", line_start=6, line_end=10),
            ],
        )
        assert len(mod.public_functions) == 1
        assert mod.public_functions[0].name == "public_fn"

    def test_public_classes_with_all(self) -> None:
        mod = ModuleInfo(
            path=Path("test.py"),
            classes=[
                ClassInfo(name="Public", line_start=1, line_end=30),
                ClassInfo(name="_Private", line_start=31, line_end=50),
            ],
            all_exports=["Public"],
        )
        assert len(mod.public_classes) == 1


# ─── PackageInfo ─────────────────────────────────────────────────────────────


class TestPackageInfo:
    """Tests for PackageInfo model."""

    def test_module_names(self, tmp_path: Path) -> None:
        root = tmp_path / "pkg"
        root.mkdir()
        (root / "__init__.py").write_text("")
        (root / "core.py").write_text("")
        sub = root / "sub"
        sub.mkdir()
        (sub / "__init__.py").write_text("")

        pkg = PackageInfo(
            name="pkg",
            root=root,
            modules=[
                ModuleInfo(path=root / "__init__.py"),
                ModuleInfo(path=root / "core.py"),
                ModuleInfo(path=sub / "__init__.py"),
            ],
        )
        names = pkg.module_names
        assert "pkg" in names
        assert "core" in names
        assert "sub" in names

    def test_public_api(self) -> None:
        pkg = PackageInfo(
            name="test",
            root=Path("/test"),
            modules=[
                ModuleInfo(
                    path=Path("/test/mod.py"),
                    functions=[
                        FunctionInfo(name="pub", line_start=1, line_end=5),
                        FunctionInfo(name="_priv", line_start=6, line_end=10),
                    ],
                )
            ],
        )
        api = pkg.public_api
        names = [s.name for s in api]
        assert "pub" in names
        assert "_priv" not in names

    def test_dependency_edges(self) -> None:
        pkg = PackageInfo(
            name="test",
            root=Path("/test"),
            dependency_edges=[("core", "utils"), ("cli", "core")],
        )
        assert len(pkg.dependency_edges) == 2


# ─── WorkspaceInfo ───────────────────────────────────────────────────────────


class TestWorkspaceInfo:
    """Tests for WorkspaceInfo model."""

    def test_create_empty(self) -> None:
        ws = WorkspaceInfo(name="my-ws", root=Path("/ws"))
        assert ws.name == "my-ws"
        assert len(ws.packages) == 0
        assert len(ws.package_edges) == 0
