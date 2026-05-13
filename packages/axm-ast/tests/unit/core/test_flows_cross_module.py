"""Unit tests for cross-module resolution helpers (no real I/O)."""

from __future__ import annotations

from collections import deque
from pathlib import Path


class TestFindSourceModuleUnit:
    """Unit tests for _find_source_module (no real I/O)."""

    def test_find_source_module_missing(self, tmp_path: Path) -> None:
        """Unknown context → returns None."""
        from axm_ast.core.flows import _find_source_module
        from axm_ast.models.nodes import PackageInfo

        pkg = PackageInfo(name="test", root=tmp_path, modules=[])

        result = _find_source_module(pkg, "nonexistent", "no.such.module")
        assert result is None


class TestTryResolveCalleeUnit:
    """Unit tests for _try_resolve_callee (no real I/O)."""

    def test_try_resolve_callee_stdlib(self, tmp_path: Path) -> None:
        """CallSite with stdlib symbol → returns None."""
        from axm_ast.core.flows import _try_resolve_callee
        from axm_ast.models.calls import CallSite
        from axm_ast.models.nodes import PackageInfo

        callee = CallSite(
            symbol="len",
            module="builtins",
            line=1,
            column=0,
            context="",
            call_expression="len(x)",
        )
        pkg = PackageInfo(name="test", root=tmp_path, modules=[])

        result = _try_resolve_callee(callee, pkg)
        assert result is None


class TestCrossModuleEdgeCasesUnit:
    """Unit edge cases for _resolve_cross_module_callees (no real I/O)."""

    def test_missing_source_module_skipped(self, tmp_path: Path) -> None:
        """Both lookups fail → callee silently skipped."""
        from axm_ast.core.flows import (
            _CrossModuleContext,
            _ResolutionScope,
            _resolve_cross_module_callees,
        )
        from axm_ast.models.calls import CallSite
        from axm_ast.models.nodes import PackageInfo

        pkg = PackageInfo(name="test", root=tmp_path, modules=[])
        ctx = _CrossModuleContext(visited=set(), queue=deque(), steps=[])
        scope = _ResolutionScope(
            current_mod="nonexistent.mod",
            current_pkg=pkg,
            original_pkg=pkg,
            depth=0,
            current_chain=["entry"],
        )

        callee = CallSite(
            symbol="unknown_fn",
            module="no.module",
            line=1,
            column=0,
            context="missing",
            call_expression="unknown_fn()",
        )
        _resolve_cross_module_callees([callee], scope, ctx)
        assert ctx.steps == []

    def test_already_visited_skipped(self, tmp_path: Path) -> None:
        """Same (dotted, symbol) pair seen → skip without duplicate FlowStep."""
        from axm_ast.core.flows import (
            _CrossModuleContext,
            _ResolutionScope,
            _resolve_cross_module_callees,
        )
        from axm_ast.models.calls import CallSite
        from axm_ast.models.nodes import PackageInfo

        pkg = PackageInfo(name="test", root=tmp_path, modules=[])
        ctx = _CrossModuleContext(
            visited={("target.module", "some_func")},
            queue=deque(),
            steps=[],
        )
        scope = _ResolutionScope(
            current_mod="caller",
            current_pkg=pkg,
            original_pkg=pkg,
            depth=0,
            current_chain=["entry"],
        )

        callee = CallSite(
            symbol="some_func",
            module="caller",
            line=1,
            column=0,
            context="",
            call_expression="some_func()",
        )
        _resolve_cross_module_callees([callee], scope, ctx)
        assert len(ctx.steps) == 0
