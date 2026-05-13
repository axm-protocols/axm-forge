"""Tests for extracted cross-module resolution helpers.

Covers _find_source_module, _try_resolve_callee, and edge cases
for _resolve_cross_module_callees after complexity refactoring.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path


class TestFindSourceModule:
    """Tests for the extracted _find_source_module helper."""

    def test_find_source_module_by_symbol(self, tmp_path: Path) -> None:
        """PackageInfo with known function → returns correct ModuleInfo."""
        from axm_ast.core.flows import _find_source_module
        from axm_ast.models.nodes import FunctionInfo, ModuleInfo, PackageInfo

        root = tmp_path / "src"
        mod_path = root / "core" / "handler.py"
        mod_path.parent.mkdir(parents=True)
        mod_path.write_text("def process(): pass")

        func = FunctionInfo(name="process", line_start=1, line_end=1)
        mod = ModuleInfo(path=mod_path, functions=[func], classes=[], imports=[])
        pkg = PackageInfo(name="test", root=root, modules=[mod])

        result = _find_source_module(pkg, "process", "")
        assert result is not None
        assert result.path == mod_path

    def test_find_source_module_by_dotted_name(self, tmp_path: Path) -> None:
        """PackageInfo + dotted module name → returns ModuleInfo via fallback."""
        from axm_ast.core.flows import _find_source_module
        from axm_ast.models.nodes import ModuleInfo, PackageInfo

        root = tmp_path / "src"
        mod_path = root / "core" / "handler.py"
        mod_path.parent.mkdir(parents=True)
        mod_path.write_text("")

        mod = ModuleInfo(path=mod_path, functions=[], classes=[], imports=[])
        pkg = PackageInfo(name="test", root=root, modules=[mod])

        result = _find_source_module(pkg, "", "core.handler")
        assert result is not None
        assert result.path == mod_path


class TestTryResolveCallee:
    """Tests for the extracted _try_resolve_callee helper."""

    def test_try_resolve_callee_local(self, tmp_path: Path) -> None:
        """CallSite with locally-defined symbol → returns None (skip local)."""
        from axm_ast.core.flows import _try_resolve_callee
        from axm_ast.models.calls import CallSite
        from axm_ast.models.nodes import FunctionInfo, ModuleInfo, PackageInfo

        root = tmp_path / "src"
        mod_path = root / "utils.py"
        mod_path.parent.mkdir(parents=True)
        mod_path.write_text("def local_fn(): pass")

        func = FunctionInfo(name="local_fn", line_start=1, line_end=1)
        mod = ModuleInfo(path=mod_path, functions=[func], classes=[], imports=[])
        pkg = PackageInfo(name="test", root=root, modules=[mod])

        callee = CallSite(
            symbol="local_fn",
            module="utils",
            line=5,
            column=0,
            context="",
            call_expression="local_fn()",
        )
        result = _try_resolve_callee(callee, pkg)
        assert result is None


class TestCrossModuleEdgeCases:
    """Edge cases for _resolve_cross_module_callees."""

    def test_reexport_missing_target_skipped(self, tmp_path: Path) -> None:
        """_follow_reexport returns None → callee skipped."""
        from axm_ast.core.flows import (
            _CrossModuleContext,
            _ResolutionScope,
            _resolve_cross_module_callees,
        )
        from axm_ast.models.calls import CallSite
        from axm_ast.models.nodes import ImportInfo, ModuleInfo, PackageInfo

        root = tmp_path / "src"
        init_py = root / "pkg" / "__init__.py"
        init_py.parent.mkdir(parents=True)
        init_py.write_text("from .missing import Widget")

        mod = ModuleInfo(
            path=init_py,
            functions=[],
            classes=[],
            imports=[ImportInfo(module=".missing", names=["Widget"])],
        )
        pkg = PackageInfo(name="test", root=root, modules=[mod])
        ctx = _CrossModuleContext(visited=set(), queue=deque(), steps=[])
        scope = _ResolutionScope(
            current_mod="pkg",
            current_pkg=pkg,
            original_pkg=pkg,
            depth=0,
            current_chain=["entry"],
        )

        callee = CallSite(
            symbol="Widget",
            module="pkg",
            line=1,
            column=0,
            context="",
            call_expression="Widget()",
        )
        _resolve_cross_module_callees([callee], scope, ctx)
        assert ctx.steps == []
