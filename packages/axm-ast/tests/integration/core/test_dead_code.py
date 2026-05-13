"""Unit tests for axm_ast.core.dead_code internals."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, create_autospec

import pytest

from axm_ast.core.dead_code import (
    DeadSymbol,
    _check_override,
    _scan_classes,
    _scan_functions,
    _scan_methods,
    _ScanContext,
    format_dead_code,
)
from axm_ast.models.nodes import (
    FunctionInfo,
    FunctionKind,
    ModuleInfo,
    PackageInfo,
)

# ---------------------------------------------------------------------------
# Helpers — _scan_functions
# ---------------------------------------------------------------------------


def _make_fn(
    name: str,
    *,
    kind: FunctionKind = FunctionKind.FUNCTION,
    decorators: list[str] | None = None,
    line_start: int = 1,
) -> FunctionInfo:
    """Build a minimal FunctionInfo stub."""
    return FunctionInfo(
        name=name,
        kind=kind,
        decorators=decorators or [],
        line_start=line_start,
        line_end=line_start + 5,
        params=[],
        return_type=None,
    )


def _make_mod(
    functions: list[FunctionInfo],
    *,
    path: Path = Path("src/pkg/mod.py"),
    all_exports: list[str] | None = None,
) -> ModuleInfo:
    """Build a minimal ModuleInfo stub."""
    return ModuleInfo(
        path=path,
        functions=functions,
        classes=[],
        imports=[],
        all_exports=all_exports,
    )


def _make_pkg(path: Path = Path("src/pkg")) -> PackageInfo:
    return cast(PackageInfo, create_autospec(PackageInfo, instance=True, path=path))


def _make_scan_ctx(
    *,
    entry_points: set[str] | None = None,
    all_refs: set[str] | None = None,
    extra_pkg: PackageInfo | None = None,
    namespace_modules: set[Path] | None = None,
) -> _ScanContext:
    """Build a _ScanContext with convenient defaults."""
    return _ScanContext(
        entry_points=entry_points or set(),
        all_refs=all_refs or set(),
        extra_pkg=extra_pkg,
        namespace_modules=namespace_modules or set(),
    )


# ---------------------------------------------------------------------------
# Helpers — _scan_classes
# ---------------------------------------------------------------------------


@dataclass
class _StubMethod:
    name: str
    line_start: int = 1
    decorators: list[str] = field(default_factory=list)


@dataclass
class _StubClass:
    name: str
    line_start: int = 1
    bases: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    methods: list[_StubMethod] = field(default_factory=list)


@dataclass
class _StubModule:
    path: Path = field(default_factory=lambda: Path("/fake/module.py"))
    classes: list[_StubClass] = field(default_factory=list)
    all_exports: list[str] | None = None


@dataclass
class _StubContext:
    entry_points: set[str] = field(default_factory=set)
    all_refs: set[str] = field(default_factory=set)
    extra_pkg: object | None = None
    namespace_modules: set[Path] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Helpers — _check_override / _scan_methods
# ---------------------------------------------------------------------------


def _method(name: str, line_start: int = 1) -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(name=name, line_start=line_start)


def _cls(name: str, bases: list[str], methods: list[Any] | None = None) -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(name=name, bases=bases, methods=methods or [])


def _override_mod(classes: list[Any], path: str = "mod.py") -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(classes=classes, path=path)


def _override_pkg(modules: list[Any]) -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(modules=modules)


def _override_ctx(**overrides: Any) -> Any:
    from types import SimpleNamespace

    defaults: dict[str, Any] = {
        "entry_points": set(),
        "all_refs": set(),
        "extra_pkg": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _no_callers(_pkg_arg: Any, _name: str) -> list[Any]:
    return []


# ---------------------------------------------------------------------------
# Helpers — _find_namespace_modules
# ---------------------------------------------------------------------------


def _make_ns_module(path: Path, *, imports: list[object] | None = None) -> MagicMock:
    """Create a minimal ModuleInfo-like mock."""
    mod = MagicMock()
    mod.path = path
    mod.imports = imports or []
    return mod


def _make_ns_import(
    *, module: str | None = None, names: list[str] | None = None
) -> MagicMock:
    """Create a minimal ImportInfo-like mock."""
    imp = MagicMock()
    imp.module = module
    imp.names = names or []
    return imp


def _make_ns_pkg(modules: list[object]) -> MagicMock:
    """Create a minimal PackageInfo-like mock."""
    pkg = MagicMock()
    pkg.modules = modules
    return pkg


def _write_source(path: Path, source: str) -> Path:
    """Write a Python source file, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


# ═══════════════════════════════════════════════════════════════════════════
# _scan_functions
# ═══════════════════════════════════════════════════════════════════════════


class TestScanFunctionsMixedLiveDead:
    """Modules with mixed live/dead functions — detection unchanged."""

    def test_dead_function_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A plain function with no callers / refs / entry-points is dead."""
        fn_dead = _make_fn("orphan_helper", line_start=10)
        fn_live = _make_fn("used_func", line_start=20)
        mod = _make_mod([fn_dead, fn_live])
        pkg = _make_pkg()
        ctx = _make_scan_ctx(all_refs={"used_func"})

        monkeypatch.setattr("axm_ast.core.callers.find_callers", lambda _pkg, _name: [])

        dead = _scan_functions(mod, pkg, ctx)

        assert len(dead) == 1
        assert dead[0].name == "orphan_helper"
        assert dead[0].kind == "function"
        assert dead[0].line == 10

    def test_entry_point_not_dead(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Functions listed in entry_points are alive."""
        fn = _make_fn("cli_main")
        mod = _make_mod([fn])
        pkg = _make_pkg()
        ctx = _make_scan_ctx(entry_points={"cli_main"})

        monkeypatch.setattr("axm_ast.core.callers.find_callers", lambda _pkg, _name: [])

        assert _scan_functions(mod, pkg, ctx) == []

    def test_ref_keeps_function_alive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Functions referenced in all_refs are alive."""
        fn = _make_fn("referenced_fn")
        mod = _make_mod([fn])
        pkg = _make_pkg()
        ctx = _make_scan_ctx(all_refs={"referenced_fn"})

        monkeypatch.setattr("axm_ast.core.callers.find_callers", lambda _pkg, _name: [])

        assert _scan_functions(mod, pkg, ctx) == []

    def test_callers_keep_function_alive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Functions with callers in the same package are alive."""
        fn = _make_fn("internal_helper")
        mod = _make_mod([fn])
        pkg = _make_pkg()
        ctx = _make_scan_ctx()

        monkeypatch.setattr(
            "axm_ast.core.callers.find_callers",
            lambda _pkg, name: ["some_caller"] if name == "internal_helper" else [],
        )

        assert _scan_functions(mod, pkg, ctx) == []

    def test_extra_pkg_callers_keep_alive(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Functions called from extra_pkg are alive."""
        fn = _make_fn("cross_pkg_helper")
        mod = _make_mod([fn])
        pkg = _make_pkg()
        extra = _make_pkg(Path("src/other_pkg"))
        ctx = _make_scan_ctx(extra_pkg=extra)

        def _find_callers(_pkg: object, name: str) -> list[str]:
            if _pkg is extra and name == "cross_pkg_helper":
                return ["ext_caller"]
            return []

        monkeypatch.setattr("axm_ast.core.callers.find_callers", _find_callers)

        assert _scan_functions(mod, pkg, ctx) == []

    def test_exempt_function_not_dead(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Exempt functions (dunder, decorated, etc.) are skipped."""
        fn = _make_fn("__repr__")
        mod = _make_mod([fn])
        pkg = _make_pkg()
        ctx = _make_scan_ctx()

        monkeypatch.setattr("axm_ast.core.callers.find_callers", lambda _pkg, _name: [])

        assert _scan_functions(mod, pkg, ctx) == []


class TestAllFunctionsAlive:
    """Module where everything has callers — empty result."""

    def test_returns_empty_when_all_alive(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fns = [_make_fn(f"fn_{i}", line_start=i * 10) for i in range(5)]
        mod = _make_mod(fns)
        pkg = _make_pkg()
        ctx = _make_scan_ctx()

        monkeypatch.setattr(
            "axm_ast.core.callers.find_callers",
            lambda _pkg, _name: ["caller"],
        )

        assert _scan_functions(mod, pkg, ctx) == []


class TestNamespacePublicFunction:
    """Public fn in namespace-imported module is not flagged as dead."""

    def test_public_fn_in_namespace_mod_not_dead(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mod_path = Path("src/pkg/api.py")
        fn = _make_fn("public_api")
        mod = _make_mod([fn], path=mod_path)
        pkg = _make_pkg()
        ctx = _make_scan_ctx(namespace_modules={mod_path})

        monkeypatch.setattr("axm_ast.core.callers.find_callers", lambda _pkg, _name: [])

        assert _scan_functions(mod, pkg, ctx) == []

    def test_private_fn_in_namespace_mod_still_dead(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Private functions in namespace modules are still flagged."""
        mod_path = Path("src/pkg/api.py")
        fn = _make_fn("_private_helper")
        mod = _make_mod([fn], path=mod_path)
        pkg = _make_pkg()
        ctx = _make_scan_ctx(namespace_modules={mod_path})

        monkeypatch.setattr("axm_ast.core.callers.find_callers", lambda _pkg, _name: [])

        dead = _scan_functions(mod, pkg, ctx)

        assert len(dead) == 1
        assert dead[0].name == "_private_helper"


# ═══════════════════════════════════════════════════════════════════════════
# _scan_classes
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def _patch_scan_classes_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch all helpers called by _scan_classes so we test its logic only."""
    monkeypatch.setattr(
        "axm_ast.core.dead_code._collect_base_class_names", lambda _pkg: set()
    )
    monkeypatch.setattr("axm_ast.core.callers.find_callers", lambda _pkg, _name: [])
    monkeypatch.setattr(
        "axm_ast.core.dead_code._is_exempt_class", lambda _cls, _mod: False
    )
    monkeypatch.setattr(
        "axm_ast.core.dead_code._has_intra_module_refs",
        lambda _name, _line, _mod: False,
    )
    monkeypatch.setattr(
        "axm_ast.core.dead_code._scan_methods",
        lambda _cls, _mod, _pkg, _ctx: [],
    )


@pytest.mark.usefixtures("_patch_scan_classes_helpers")
class TestScanClassesDetection:
    """Modules with mixed live/dead classes — detection unchanged."""

    def test_class_in_entry_points_not_flagged(self) -> None:
        """A class listed in entry_points is skipped entirely."""
        cls = _StubClass(name="Router")
        mod = _StubModule(classes=[cls])
        ctx = _StubContext(entry_points={"Router"})

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        assert all(s.name != "Router" for s in result)

    def test_class_in_all_refs_not_flagged(self) -> None:
        """A class present in all_refs is considered alive."""
        cls = _StubClass(name="Config")
        mod = _StubModule(classes=[cls])
        ctx = _StubContext(all_refs={"Config"})

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        assert all(s.name != "Config" for s in result)

    def test_class_with_callers_not_flagged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A class with callers in the primary package is alive."""
        cls = _StubClass(name="Service")
        mod = _StubModule(classes=[cls])
        ctx = _StubContext()

        monkeypatch.setattr(
            "axm_ast.core.callers.find_callers",
            lambda _pkg, name: ["some_caller"] if name == "Service" else [],
        )

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        assert all(s.name != "Service" for s in result)

    def test_class_with_callers_in_extra_pkg_not_flagged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A class found only via extra_pkg callers is alive."""
        cls = _StubClass(name="Helper")
        mod = _StubModule(classes=[cls])
        extra = MagicMock()
        ctx = _StubContext(extra_pkg=extra)

        def _find_callers(_pkg: object, name: str) -> list[str]:
            if _pkg is extra and name == "Helper":
                return ["ext_caller"]
            return []

        monkeypatch.setattr("axm_ast.core.callers.find_callers", _find_callers)

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        assert all(s.name != "Helper" for s in result)

    def test_exempt_class_not_flagged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An exempt class (decorated, protocol, etc.) is not dead."""
        cls = _StubClass(name="Proto")
        mod = _StubModule(classes=[cls])
        ctx = _StubContext()

        monkeypatch.setattr(
            "axm_ast.core.dead_code._is_exempt_class", lambda c, m: True
        )

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        assert all(s.name != "Proto" for s in result)

    def test_truly_dead_class_flagged(self) -> None:
        """A class with no callers, not exempt, no intra-module refs is dead."""
        cls = _StubClass(name="Orphan", line_start=42)
        mod = _StubModule(classes=[cls])
        ctx = _StubContext()

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        dead_names = [s.name for s in result]
        assert "Orphan" in dead_names
        orphan = next(s for s in result if s.name == "Orphan")
        assert orphan.kind == "class"
        assert orphan.line == 42

    def test_mixed_live_and_dead_classes(self) -> None:
        """Only truly dead classes are flagged; alive ones are skipped."""
        alive_cls = _StubClass(name="Alive")
        dead_cls = _StubClass(name="Dead", line_start=10)
        mod = _StubModule(classes=[alive_cls, dead_cls])
        ctx = _StubContext(all_refs={"Alive"})

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        dead_names = [s.name for s in result]
        assert "Alive" not in dead_names
        assert "Dead" in dead_names


@pytest.mark.usefixtures("_patch_scan_classes_helpers")
class TestScanClassesEdgeCases:
    def test_class_used_as_base_not_flagged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A class that appears in the all_bases set is not flagged."""
        parent = _StubClass(name="BaseModel")
        child = _StubClass(name="Child", bases=["BaseModel"])
        mod = _StubModule(classes=[parent, child])
        ctx = _StubContext()

        monkeypatch.setattr(
            "axm_ast.core.dead_code._collect_base_class_names",
            lambda _pkg: {"BaseModel"},
        )

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        dead_names = [s.name for s in result]
        assert "BaseModel" not in dead_names

    def test_class_with_intra_module_refs_not_flagged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A class referenced only within same module is not dead."""
        cls = _StubClass(name="InternalHelper", line_start=5)
        mod = _StubModule(classes=[cls])
        ctx = _StubContext()

        monkeypatch.setattr(
            "axm_ast.core.dead_code._has_intra_module_refs",
            lambda name, _line, _mod: name == "InternalHelper",
        )

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        assert all(s.name != "InternalHelper" for s in result)

    def test_live_class_with_dead_methods(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A live class (via callers) still reports dead methods from _scan_methods."""
        cls = _StubClass(name="LiveClass")
        mod = _StubModule(classes=[cls])
        ctx = _StubContext()

        monkeypatch.setattr(
            "axm_ast.core.callers.find_callers",
            lambda _pkg, name: ["a_caller"] if name == "LiveClass" else [],
        )

        dead_method = DeadSymbol(
            name="LiveClass.unused_method",
            module_path=str(mod.path),
            line=20,
            kind="method",
        )
        monkeypatch.setattr(
            "axm_ast.core.dead_code._scan_methods",
            lambda _cls, _mod, _pkg, _ctx: [dead_method],
        )

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        assert all(s.kind != "class" for s in result)
        assert len(result) == 1
        assert result[0].name == "LiveClass.unused_method"
        assert result[0].kind == "method"

    def test_scan_methods_called_for_non_skipped_classes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_scan_methods is invoked for classes not short-circuited by continue."""
        cls_skipped = _StubClass(name="Skipped")
        cls_checked = _StubClass(name="Checked")
        mod = _StubModule(classes=[cls_skipped, cls_checked])
        ctx = _StubContext(entry_points={"Skipped"})

        calls: list[str] = []

        def _track_scan_methods(c: Any, _mod: Any, _pkg: Any, _ctx: Any) -> list[Any]:
            calls.append(c.name)
            return []

        monkeypatch.setattr("axm_ast.core.dead_code._scan_methods", _track_scan_methods)

        _scan_classes(cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx))

        assert "Skipped" not in calls
        assert "Checked" in calls


# ═══════════════════════════════════════════════════════════════════════════
# _check_override / _scan_methods
# ═══════════════════════════════════════════════════════════════════════════


class TestCheckOverrideExternal:
    """_check_override must return True when the base class is external."""

    def test_override_external_base_not_dead(self) -> None:
        """Class inheriting ExternalBase (not in package) with do_GET."""
        handler = _cls("MyHandler", bases=["ExternalBase"], methods=[_method("do_GET")])
        pkg = _override_pkg(modules=[_override_mod(classes=[handler])])

        assert _check_override("do_GET", handler, pkg) is True

    def test_override_external_base_log_message(self) -> None:
        """Class inheriting ExternalBase with log_message."""
        handler = _cls(
            "MyHandler", bases=["ExternalBase"], methods=[_method("log_message")]
        )
        pkg = _override_pkg(modules=[_override_mod(classes=[handler])])

        assert _check_override("log_message", handler, pkg) is True

    def test_override_inpackage_base_still_checked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Class inheriting in-package Base with uncalled method — method IS flagged."""
        base = _cls("Base", bases=[], methods=[_method("process")])
        child = _cls("Child", bases=["Base"], methods=[_method("process")])
        pkg = _override_pkg(modules=[_override_mod(classes=[base, child])])

        monkeypatch.setattr("axm_ast.core.callers.find_callers", _no_callers)

        assert _check_override("process", child, pkg) is False


class TestScanMethodsExternalOverride:
    """_scan_methods must not flag methods overriding external bases."""

    def test_http_handler_methods_not_dead(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BaseHTTPRequestHandler subclass — do_GET and log_message not flagged."""
        handler = _cls(
            "MyHandler",
            bases=["BaseHTTPRequestHandler"],
            methods=[_method("do_GET", 10), _method("log_message", 20)],
        )
        mod = _override_mod(classes=[handler], path="handlers.py")
        pkg = _override_pkg(modules=[mod])

        monkeypatch.setattr("axm_ast.core.callers.find_callers", _no_callers)
        monkeypatch.setattr(
            "axm_ast.core.dead_code._is_exempt_function", lambda *a, **kw: False
        )

        dead = _scan_methods(handler, mod, pkg, _override_ctx())
        dead_names = {d.name for d in dead}

        assert "MyHandler.do_GET" not in dead_names
        assert "MyHandler.log_message" not in dead_names

    def test_thread_run_not_dead(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Thread subclass with run() override — not flagged."""
        worker = _cls("Worker", bases=["Thread"], methods=[_method("run", 5)])
        mod = _override_mod(classes=[worker], path="workers.py")
        pkg = _override_pkg(modules=[mod])

        monkeypatch.setattr("axm_ast.core.callers.find_callers", _no_callers)
        monkeypatch.setattr(
            "axm_ast.core.dead_code._is_exempt_function", lambda *a, **kw: False
        )

        dead = _scan_methods(worker, mod, pkg, _override_ctx())
        dead_names = {d.name for d in dead}

        assert "Worker.run" not in dead_names


class TestOverrideEdgeCases:
    """Boundary conditions for external-base override heuristic."""

    def test_mixed_bases_external_method_exempted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In-pkg + external base — method only on external is exempted."""
        in_pkg_base = _cls("InPkgBase", bases=[], methods=[])
        child = _cls(
            "Foo",
            bases=["InPkgBase", "ExternalBase"],
            methods=[_method("external_method", 10)],
        )
        mod = _override_mod(classes=[in_pkg_base, child], path="mixed.py")
        pkg = _override_pkg(modules=[mod])

        monkeypatch.setattr("axm_ast.core.callers.find_callers", _no_callers)
        monkeypatch.setattr(
            "axm_ast.core.dead_code._is_exempt_function", lambda *a, **kw: False
        )

        dead = _scan_methods(child, mod, pkg, _override_ctx())
        dead_names = {d.name for d in dead}

        assert "Foo.external_method" not in dead_names

    def test_private_method_on_external_base_still_flagged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Private method on external base — still flagged."""
        child = _cls(
            "Foo",
            bases=["ExternalBase"],
            methods=[_method("_internal_helper", 10)],
        )
        mod = _override_mod(classes=[child], path="priv.py")
        pkg = _override_pkg(modules=[mod])

        monkeypatch.setattr("axm_ast.core.callers.find_callers", _no_callers)
        monkeypatch.setattr(
            "axm_ast.core.dead_code._is_exempt_function", lambda *a, **kw: False
        )

        dead = _scan_methods(child, mod, pkg, _override_ctx())
        dead_names = {d.name for d in dead}

        assert "Foo._internal_helper" in dead_names

    def test_dunder_override_external_base_presumed_live(self) -> None:
        """Dunder method overriding external base — presumed live (not private)."""
        child = _cls(
            "MyModel",
            bases=["ExternalBase"],
            methods=[_method("__init__", 5)],
        )
        pkg = _override_pkg(modules=[_override_mod(classes=[child])])

        assert _check_override("__init__", child, pkg) is True

    def test_external_base_truly_dead_method(self) -> None:
        """All bases external, brand-new method — acceptable false negative."""
        child = _cls(
            "Foo",
            bases=["ExternalBase"],
            methods=[_method("totally_new_method", 10)],
        )
        pkg = _override_pkg(modules=[_override_mod(classes=[child])])

        assert _check_override("totally_new_method", child, pkg) is True


# ═══════════════════════════════════════════════════════════════════════════
# _find_namespace_modules
# ═══════════════════════════════════════════════════════════════════════════


class TestLazyImportNamespaceDetection:
    """Lazy `from pkg import mod` inside function bodies detects namespace modules."""

    def test_lazy_import_namespace_module_detected(self, tmp_path: Path) -> None:
        from axm_ast.core.dead_code import _find_namespace_modules

        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()

        mod_a_path = _write_source(
            pkg_dir / "caller.py",
            "def do_work():\n    from mypkg import utils\n    utils.func()\n",
        )
        mod_b_path = _write_source(
            pkg_dir / "utils.py",
            "def func():\n    return 42\n",
        )

        mod_a = _make_ns_module(mod_a_path, imports=[])
        mod_b = _make_ns_module(mod_b_path, imports=[])
        pkg = _make_ns_pkg([mod_a, mod_b])

        result = _find_namespace_modules(pkg)

        assert mod_b_path in result

    def test_lazy_import_private_fn_module_still_namespace(
        self, tmp_path: Path
    ) -> None:
        from axm_ast.core.dead_code import _find_namespace_modules

        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()

        mod_a_path = _write_source(
            pkg_dir / "caller.py",
            "def do_work():\n    from mypkg import utils\n    utils.func()\n",
        )
        mod_b_path = _write_source(
            pkg_dir / "utils.py",
            "def _helper():\n    return 1\n\ndef func():\n    return _helper()\n",
        )

        mod_a = _make_ns_module(mod_a_path, imports=[])
        mod_b = _make_ns_module(mod_b_path, imports=[])
        pkg = _make_ns_pkg([mod_a, mod_b])

        result = _find_namespace_modules(pkg)

        assert mod_b_path in result

    def test_lazy_symbol_import_not_namespace(self, tmp_path: Path) -> None:
        """from pkg.mod import func (symbol, not module) → mod NOT namespace."""
        from axm_ast.core.dead_code import _find_namespace_modules

        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()

        mod_a_path = _write_source(
            pkg_dir / "caller.py",
            "def do_work():\n    from mypkg.utils import func\n    func()\n",
        )
        mod_b_path = _write_source(
            pkg_dir / "utils.py",
            "def func():\n    return 42\n",
        )

        mod_a = _make_ns_module(mod_a_path, imports=[])
        mod_b = _make_ns_module(mod_b_path, imports=[])
        pkg = _make_ns_pkg([mod_a, mod_b])

        result = _find_namespace_modules(pkg)

        assert mod_b_path not in result

    def test_both_module_level_and_lazy(self, tmp_path: Path) -> None:
        from axm_ast.core.dead_code import _find_namespace_modules

        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()

        mod_a_path = _write_source(
            pkg_dir / "mod_a.py",
            "from mypkg import helpers\nhelpers.run()\n",
        )
        mod_c_path = _write_source(
            pkg_dir / "mod_c.py",
            "def work():\n    from mypkg import helpers\n    helpers.run()\n",
        )
        mod_b_path = _write_source(
            pkg_dir / "helpers.py",
            "def run():\n    pass\n",
        )

        imp_a = _make_ns_import(module="mypkg", names=["helpers"])
        mod_a = _make_ns_module(mod_a_path, imports=[imp_a])
        mod_c = _make_ns_module(mod_c_path, imports=[])
        mod_b = _make_ns_module(mod_b_path, imports=[])
        pkg = _make_ns_pkg([mod_a, mod_c, mod_b])

        result = _find_namespace_modules(pkg)

        assert mod_b_path in result

    def test_lazy_import_with_alias(self, tmp_path: Path) -> None:
        from axm_ast.core.dead_code import _find_namespace_modules

        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()

        mod_a_path = _write_source(
            pkg_dir / "caller.py",
            "def work():\n    from mypkg import utils as u\n    u.func()\n",
        )
        mod_b_path = _write_source(
            pkg_dir / "utils.py",
            "def func():\n    return 1\n",
        )

        mod_a = _make_ns_module(mod_a_path, imports=[])
        mod_b = _make_ns_module(mod_b_path, imports=[])
        pkg = _make_ns_pkg([mod_a, mod_b])

        result = _find_namespace_modules(pkg)

        assert mod_b_path in result

    def test_lazy_import_in_nested_function(self, tmp_path: Path) -> None:
        from axm_ast.core.dead_code import _find_namespace_modules

        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()

        mod_a_path = _write_source(
            pkg_dir / "caller.py",
            (
                "def outer():\n"
                "    def inner():\n"
                "        from mypkg import utils\n"
                "        utils.func()\n"
            ),
        )
        mod_b_path = _write_source(
            pkg_dir / "utils.py",
            "def func():\n    return 1\n",
        )

        mod_a = _make_ns_module(mod_a_path, imports=[])
        mod_b = _make_ns_module(mod_b_path, imports=[])
        pkg = _make_ns_pkg([mod_a, mod_b])

        result = _find_namespace_modules(pkg)

        assert mod_b_path in result

    def test_empty_package_returns_empty_set(self) -> None:
        from axm_ast.core.dead_code import _find_namespace_modules

        pkg = _make_ns_pkg([])
        result = _find_namespace_modules(pkg)

        assert result == set()

    def test_no_imports_returns_empty_set(self, tmp_path: Path) -> None:
        from axm_ast.core.dead_code import _find_namespace_modules

        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()

        mod_a_path = _write_source(
            pkg_dir / "alpha.py",
            "def foo():\n    return 1\n",
        )
        mod_b_path = _write_source(
            pkg_dir / "beta.py",
            "x = 42\n",
        )

        mod_a = _make_ns_module(mod_a_path, imports=[])
        mod_b = _make_ns_module(mod_b_path, imports=[])
        pkg = _make_ns_pkg([mod_a, mod_b])

        result = _find_namespace_modules(pkg)

        assert result == set()

    def test_mixed_bare_and_from_imports_single_entry(self, tmp_path: Path) -> None:
        from axm_ast.core.dead_code import _find_namespace_modules

        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()

        mod_a_path = _write_source(
            pkg_dir / "caller.py",
            "import mypkg.utils\nfrom mypkg import utils\n",
        )
        mod_b_path = _write_source(
            pkg_dir / "utils.py",
            "def func():\n    return 1\n",
        )

        imp_bare = _make_ns_import(module="mypkg.utils", names=[])
        imp_from = _make_ns_import(module="mypkg", names=["utils"])
        mod_a = _make_ns_module(mod_a_path, imports=[imp_bare, imp_from])
        mod_b = _make_ns_module(mod_b_path, imports=[])
        pkg = _make_ns_pkg([mod_a, mod_b])

        result = _find_namespace_modules(pkg)

        assert mod_b_path in result
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════════════════
# format_dead_code
# ═══════════════════════════════════════════════════════════════════════════


class TestFormatDeadCode:
    """Test output formatting."""

    def test_format_empty(self) -> None:
        """Empty results → clean message."""
        assert format_dead_code([]) == "\u2705 No dead code detected."

    def test_format_results(self) -> None:
        """Results → grouped output."""
        results = [
            DeadSymbol(name="foo", module_path="/a/b.py", line=10, kind="function"),
            DeadSymbol(name="bar", module_path="/a/b.py", line=20, kind="method"),
            DeadSymbol(name="baz", module_path="/a/c.py", line=5, kind="class"),
        ]
        output = format_dead_code(results)
        assert "3 dead symbol(s)" in output
        assert "foo" in output
        assert "bar" in output
        assert "baz" in output
        assert "/a/b.py" in output
        assert "/a/c.py" in output
