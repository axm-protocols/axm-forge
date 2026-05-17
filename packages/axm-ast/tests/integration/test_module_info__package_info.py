"""Tests for extracted cross-module resolution helpers.

Covers _find_source_module, _try_resolve_callee, and edge cases
for _resolve_cross_module_callees after complexity refactoring.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    ModuleInfo,
    PackageInfo,
)


def test_find_source_module_by_dotted_name(tmp_path: Path) -> None:
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


def test_module_names(tmp_path: Path) -> None:
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


def test_public_api_aggregates():
    mod = ModuleInfo(
        path=Path("src/mypkg/core.py"),
        functions=[FunctionInfo(name="run", line_start=1, line_end=1)],
        classes=[ClassInfo(name="Engine", line_start=2, line_end=10)],
    )
    pkg = PackageInfo(name="mypkg", root=Path("src/mypkg"), modules=[mod])
    api = pkg.public_api
    assert len(api) >= 1
