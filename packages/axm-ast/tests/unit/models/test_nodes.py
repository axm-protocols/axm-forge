"""Unit tests for axm_ast.models.nodes (pure, no I/O)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from axm_ast.core.analyzer import find_module_for_symbol, search_symbols
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

# ── ClassInfo ──


def test_basic_class():
    cls = ClassInfo(name="Foo", line_start=1, line_end=10)
    assert cls.name == "Foo"
    assert cls.is_public is True
    assert cls.bases == []
    assert cls.methods == []


def test_class_info_rejects_extra() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ClassInfo(name="X", line_start=1, line_end=2, oops=True)  # type: ignore[call-arg]


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


# ── FunctionInfo ──


def test_is_public() -> None:
    fn = FunctionInfo(name="greet", line_start=1, line_end=5)
    assert fn.is_public is True


def test_is_private() -> None:
    fn = FunctionInfo(name="_helper", line_start=1, line_end=5)
    assert fn.is_public is False


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


def test_basic_function():
    fn = FunctionInfo(name="foo", line_start=1, line_end=3)
    assert fn.name == "foo"
    assert fn.kind == FunctionKind.FUNCTION
    assert fn.is_public is True
    assert fn.is_async is False


def test_all_kinds():
    for kind in FunctionKind:
        fn = FunctionInfo(name="x", kind=kind, line_start=1, line_end=1)
        assert fn.kind == kind


def test_class_with_methods():
    method = FunctionInfo(
        name="parse",
        kind=FunctionKind.METHOD,
        line_start=3,
        line_end=10,
    )
    cls = ClassInfo(name="Parser", methods=[method], line_start=1, line_end=10)
    assert len(cls.methods) == 1
    assert cls.methods[0].kind == FunctionKind.METHOD


def _make_module(
    name: str,
    *,
    functions: list[FunctionInfo] | None = None,
    classes: list[ClassInfo] | None = None,
    variables: list[VariableInfo] | None = None,
) -> ModuleInfo:
    return ModuleInfo(
        name=name,
        path=Path(f"{name.replace('.', '/')}.py"),
        imports=[],
        functions=functions or [],
        classes=classes or [],
        variables=variables or [],
    )


def test_returns_name_matching_class_only_matching_methods() -> None:
    mod = ModuleInfo(
        path=Path("edge.py"),
        classes=[
            ClassInfo(
                name="User",
                bases=[],
                line_start=1,
                line_end=20,
                methods=[
                    FunctionInfo(
                        name="UserSerializer",
                        kind=FunctionKind.METHOD,
                        return_type="str",
                        line_start=3,
                        line_end=5,
                    ),
                    FunctionInfo(
                        name="get_id",
                        kind=FunctionKind.METHOD,
                        return_type="int",
                        line_start=7,
                        line_end=9,
                    ),
                ],
            ),
        ],
    )
    pkg = PackageInfo(name="edge", root=Path("edge"), modules=[mod])
    results = search_symbols(pkg, name="User", returns="str")
    names = [sym.name for _, sym in results]
    assert "User" not in names
    assert "UserSerializer" in names
    assert "get_id" not in names


def test_init_module_path() -> None:
    fn = FunctionInfo(
        name="greet",
        kind=FunctionKind.FUNCTION,
        line_start=5,
        line_end=7,
        decorators=[],
    )
    mod = _make_module("pkg.__init__", functions=[fn])
    pkg = PackageInfo(name="pkg", root=Path("/tmp/pkg"), modules=[mod])

    results = search_symbols(pkg, name="greet")
    assert len(results) == 1
    assert results[0][0] == "pkg.__init__"


def test_signature_with_params() -> None:
    fn = FunctionInfo(
        name="greet",
        params=[ParameterInfo(name="name", annotation="str")],
        return_type="str",
        line_start=1,
        line_end=3,
    )
    assert fn.signature == "def greet(name: str) -> str"


# ── FunctionKind ──


class TestFunctionKind:
    """Tests for FunctionKind enum."""

    def test_all_values(self) -> None:
        actual = {k.value for k in FunctionKind}
        required = {"function", "method", "property", "classmethod", "staticmethod"}
        assert required.issubset(actual)

    def test_str_enum(self) -> None:
        assert str(FunctionKind.FUNCTION) == "function"
        assert FunctionKind("method") == FunctionKind.METHOD


# ── ImportInfo ──


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


class TestImportInfoFromModels:
    """Tests for ImportInfo model."""

    def test_import_with_alias(self):
        imp = ImportInfo(module="numpy", names=["numpy"], alias="np")
        assert imp.alias == "np"

    def test_star_import(self):
        imp = ImportInfo(module="os", names=["*"])
        assert "*" in imp.names


# ── ModuleInfo ──


def test_empty_module():
    mod = ModuleInfo(path=Path("test.py"))
    assert mod.functions == []
    assert mod.classes == []
    assert mod.all_exports is None


def test_module_info_rejects_extra() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ModuleInfo(path=Path("x.py"), nope=1)  # type: ignore[call-arg]


def test_public_classes_with_all() -> None:
    mod = ModuleInfo(
        path=Path("test.py"),
        classes=[
            ClassInfo(name="Public", line_start=1, line_end=30),
            ClassInfo(name="_Private", line_start=31, line_end=50),
        ],
        all_exports=["Public"],
    )
    assert len(mod.public_classes) == 1


def test_public_classes_no_all():
    mod = ModuleInfo(
        path=Path("test.py"),
        classes=[
            ClassInfo(name="Public", line_start=1, line_end=5),
            ClassInfo(name="_Private", line_start=6, line_end=10),
        ],
    )
    assert len(mod.public_classes) == 1


# ── PackageInfo ──


def test_public_api_aggregates():
    mod = ModuleInfo(
        path=Path("src/mypkg/core.py"),
        functions=[FunctionInfo(name="run", line_start=1, line_end=1)],
        classes=[ClassInfo(name="Engine", line_start=2, line_end=10)],
    )
    pkg = PackageInfo(name="mypkg", root=Path("src/mypkg"), modules=[mod])
    api = pkg.public_api
    assert len(api) >= 1


def test_dependency_edges() -> None:
    pkg = PackageInfo(
        name="test",
        root=Path("/test"),
        dependency_edges=[("core", "utils"), ("cli", "core")],
    )
    assert len(pkg.dependency_edges) == 2


def test_empty_package():
    pkg = PackageInfo(name="mypkg", root=Path("src/mypkg"))
    assert pkg.modules == []
    assert pkg.public_api == []
    assert pkg.module_names == []


def test_public_api() -> None:
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


@pytest.fixture()
def sample_var() -> VariableInfo:
    return VariableInfo(name="MY_VAR", line=25)


@pytest.fixture()
def sample_module(
    sample_func: FunctionInfo, sample_class: ClassInfo, sample_var: VariableInfo
) -> ModuleInfo:
    return ModuleInfo(
        path=Path("mod.py"),
        functions=[sample_func],
        classes=[sample_class],
        variables=[sample_var],
    )


@pytest.fixture()
def sample_package(sample_module: ModuleInfo) -> PackageInfo:
    return PackageInfo(name="pkg", root=Path("pkg"), modules=[sample_module])


def test_find_by_object_identity(
    sample_package: PackageInfo, sample_func: FunctionInfo
) -> None:
    mod = find_module_for_symbol(sample_package, sample_func)
    assert mod is not None
    assert any(f.name == "my_func" for f in mod.functions)


def test_unknown_object_returns_none(sample_package: PackageInfo) -> None:
    other = FunctionInfo(name="other", line_start=1, line_end=2, decorators=[])
    assert find_module_for_symbol(sample_package, other) is None


# ── ParameterInfo ──


def test_parameter_info_rejects_extra() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ParameterInfo(name="x", bad="field")  # type: ignore[call-arg]


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


class TestParameterInfoFromModels:
    """Tests for ParameterInfo model."""

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


# ── VariableInfo ──


class TestVariableInfo:
    """Tests for VariableInfo model."""

    def test_create(self) -> None:
        v = VariableInfo(name="__all__", line=5)
        assert v.name == "__all__"
        assert v.annotation is None


class TestVariableInfoFromModels:
    """Tests for VariableInfo model."""

    def test_annotated_variable(self):
        v = VariableInfo(name="x", annotation="int", value_repr="42", line=1)
        assert v.annotation == "int"
        assert v.value_repr == "42"


# ── WorkspaceInfo ──


class TestWorkspaceInfo:
    """Tests for WorkspaceInfo model."""

    def test_create_empty(self) -> None:
        ws = WorkspaceInfo(name="my-ws", root=Path("/ws"))
        assert ws.name == "my-ws"
        assert len(ws.packages) == 0
        assert len(ws.package_edges) == 0


# ── FunctionInfo.signature Annotated-stripping (public surface) ──


class TestFunctionInfoSignatureStrips:
    """Functional tests: FunctionInfo.model_post_init strips Annotated.

    These tests drive Annotated-stripping through the public
    ``FunctionInfo.signature`` surface (computed in ``model_post_init``)
    rather than reaching into the private ``_strip_annotated`` helper.
    """

    def test_function_info_signature_strips_annotated(self) -> None:
        info = FunctionInfo(
            name="greet",
            line_start=1,
            line_end=3,
            docstring=None,
            params=[
                ParameterInfo(
                    name="name", annotation="Annotated[str, Parameter(help='user')]"
                ),
            ],
            return_type="None",
            is_async=False,
        )
        assert info.signature is not None
        assert "Annotated" not in info.signature
        assert "name: str" in info.signature

    def test_search_cyclopts_function(self) -> None:
        """Simulate a cyclopts-annotated CLI function parsed result."""
        info = FunctionInfo(
            name="serve",
            line_start=10,
            line_end=30,
            docstring="Start server.",
            params=[
                ParameterInfo(
                    name="host", annotation="Annotated[str, Parameter(help='Host')]"
                ),
                ParameterInfo(
                    name="port", annotation="Annotated[int, Parameter(help='Port')]"
                ),
                ParameterInfo(name="verbose", annotation="bool", default="False"),
            ],
            return_type="None",
            is_async=False,
        )
        assert info.signature is not None
        assert "Annotated" not in info.signature
        assert "host: str" in info.signature
        assert "port: int" in info.signature
        assert "verbose: bool" in info.signature

    def test_strip_nested_type(self) -> None:
        """Annotated[dict[str, int], ...] preserves the inner generic."""
        info = FunctionInfo(
            name="f",
            line_start=1,
            line_end=1,
            params=[
                ParameterInfo(name="p", annotation="Annotated[dict[str, int], Meta()]"),
            ],
        )
        assert info.signature is not None
        assert "Annotated" not in info.signature
        assert "p: dict[str, int]" in info.signature

    def test_strip_multiline_annotated(self) -> None:
        """Annotated[...] spread across multiple lines is still stripped."""
        raw = "Annotated[\n    str,\n    Parameter(help='...'),\n]"
        info = FunctionInfo(
            name="f",
            line_start=1,
            line_end=1,
            params=[ParameterInfo(name="p", annotation=raw)],
        )
        assert info.signature is not None
        assert "Annotated" not in info.signature
        assert "p: str" in info.signature

    def test_no_strip_plain_type(self) -> None:
        """A bare type passes through unchanged."""
        info = FunctionInfo(
            name="f",
            line_start=1,
            line_end=1,
            params=[ParameterInfo(name="p", annotation="str")],
        )
        assert info.signature == "def f(p: str)"

    def test_no_strip_generic(self) -> None:
        """Generics that are not Annotated are preserved verbatim."""
        info = FunctionInfo(
            name="f",
            line_start=1,
            line_end=1,
            params=[ParameterInfo(name="p", annotation="list[str]")],
        )
        assert info.signature == "def f(p: list[str])"


class TestFunctionInfoSignatureStripsEdgeCases:
    """Edge-case coverage for Annotated-stripping via FunctionInfo.signature."""

    def test_multiple_annotated_params(self) -> None:
        """Function with 3+ Annotated parameters — all stripped independently."""
        info = FunctionInfo(
            name="f",
            line_start=1,
            line_end=5,
            docstring=None,
            params=[
                ParameterInfo(name="a", annotation="Annotated[str, X]"),
                ParameterInfo(name="b", annotation="Annotated[int, Y]"),
                ParameterInfo(name="c", annotation="Annotated[float, Z]"),
            ],
            return_type=None,
            is_async=False,
        )
        assert info.signature is not None
        assert "Annotated" not in info.signature
        assert "a: str" in info.signature
        assert "b: int" in info.signature
        assert "c: float" in info.signature

    def test_annotated_with_multiple_metadata(self) -> None:
        """Annotated[T, A, B, C] keeps only T."""
        info = FunctionInfo(
            name="f",
            line_start=1,
            line_end=1,
            params=[ParameterInfo(name="p", annotation="Annotated[str, A, B, C]")],
        )
        assert info.signature is not None
        assert "Annotated" not in info.signature
        assert "p: str" in info.signature

    def test_annotated_as_return_type(self) -> None:
        """Return type Annotated[bool, ...] should also be stripped."""
        info = FunctionInfo(
            name="check",
            line_start=1,
            line_end=3,
            docstring=None,
            params=[],
            return_type="Annotated[bool, Meta()]",
            is_async=False,
        )
        assert info.signature is not None
        assert "Annotated" not in info.signature
        assert "-> bool" in info.signature

    def test_empty_annotated(self) -> None:
        """Annotated[str] with single arg (unusual but valid)."""
        info = FunctionInfo(
            name="f",
            line_start=1,
            line_end=1,
            params=[ParameterInfo(name="p", annotation="Annotated[str]")],
        )
        assert info.signature is not None
        assert "Annotated" not in info.signature
        assert "p: str" in info.signature


# ---------------------------------------------------------------------------
# ModuleInfo.public_functions tests (merged from tests/unit/test_models.py)
# ---------------------------------------------------------------------------


def test_public_functions_with_all() -> None:
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


def test_public_functions_without_all() -> None:
    mod = ModuleInfo(
        path=Path("test.py"),
        functions=[
            FunctionInfo(name="public_fn", line_start=1, line_end=5),
            FunctionInfo(name="_private_fn", line_start=6, line_end=10),
        ],
    )
    assert len(mod.public_functions) == 1
    assert mod.public_functions[0].name == "public_fn"


def test_public_functions_with_all_extra() -> None:
    """With __all__, listed _private names are still public."""
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
