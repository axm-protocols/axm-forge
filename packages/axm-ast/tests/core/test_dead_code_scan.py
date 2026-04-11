from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import create_autospec

import pytest

from axm_ast.core.dead_code import _scan_functions, _ScanContext
from axm_ast.models.nodes import (
    FunctionInfo,
    FunctionKind,
    ModuleInfo,
    PackageInfo,
)

# ---------------------------------------------------------------------------
# Helpers
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


def _make_ctx(
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
# _scan_functions — mixed live/dead
# ---------------------------------------------------------------------------


class TestScanFunctionsMixedLiveDead:
    """Modules with mixed live/dead functions — detection unchanged."""

    def test_dead_function_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A plain function with no callers / refs / entry-points is dead."""
        fn_dead = _make_fn("orphan_helper", line_start=10)
        fn_live = _make_fn("used_func", line_start=20)
        mod = _make_mod([fn_dead, fn_live])
        pkg = _make_pkg()
        ctx = _make_ctx(all_refs={"used_func"})

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
        ctx = _make_ctx(entry_points={"cli_main"})

        monkeypatch.setattr("axm_ast.core.callers.find_callers", lambda _pkg, _name: [])

        assert _scan_functions(mod, pkg, ctx) == []

    def test_ref_keeps_function_alive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Functions referenced in all_refs are alive."""
        fn = _make_fn("referenced_fn")
        mod = _make_mod([fn])
        pkg = _make_pkg()
        ctx = _make_ctx(all_refs={"referenced_fn"})

        monkeypatch.setattr("axm_ast.core.callers.find_callers", lambda _pkg, _name: [])

        assert _scan_functions(mod, pkg, ctx) == []

    def test_callers_keep_function_alive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Functions with callers in the same package are alive."""
        fn = _make_fn("internal_helper")
        mod = _make_mod([fn])
        pkg = _make_pkg()
        ctx = _make_ctx()

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
        ctx = _make_ctx(extra_pkg=extra)

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
        ctx = _make_ctx()

        monkeypatch.setattr("axm_ast.core.callers.find_callers", lambda _pkg, _name: [])

        assert _scan_functions(mod, pkg, ctx) == []


# ---------------------------------------------------------------------------
# Edge case: all functions alive
# ---------------------------------------------------------------------------


class TestAllFunctionsAlive:
    """Module where everything has callers — empty result."""

    def test_returns_empty_when_all_alive(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fns = [_make_fn(f"fn_{i}", line_start=i * 10) for i in range(5)]
        mod = _make_mod(fns)
        pkg = _make_pkg()
        ctx = _make_ctx()

        # Every function has at least one caller
        monkeypatch.setattr(
            "axm_ast.core.callers.find_callers",
            lambda _pkg, _name: ["caller"],
        )

        assert _scan_functions(mod, pkg, ctx) == []


# ---------------------------------------------------------------------------
# Edge case: namespace public function
# ---------------------------------------------------------------------------


class TestNamespacePublicFunction:
    """Public fn in namespace-imported module is not flagged as dead."""

    def test_public_fn_in_namespace_mod_not_dead(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mod_path = Path("src/pkg/api.py")
        fn = _make_fn("public_api")
        mod = _make_mod([fn], path=mod_path)
        pkg = _make_pkg()
        ctx = _make_ctx(namespace_modules={mod_path})

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
        ctx = _make_ctx(namespace_modules={mod_path})

        monkeypatch.setattr("axm_ast.core.callers.find_callers", lambda _pkg, _name: [])

        dead = _scan_functions(mod, pkg, ctx)

        assert len(dead) == 1
        assert dead[0].name == "_private_helper"
