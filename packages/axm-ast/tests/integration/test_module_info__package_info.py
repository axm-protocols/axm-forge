"""Public-API drivers for cross-module resolution edge cases.

Previously imported ``axm_ast.core.flows._find_source_module``,
``_CrossModuleContext``, ``_ResolutionScope`` and
``_resolve_cross_module_callees`` directly. The same scenarios are now
exercised through ``find_module_for_symbol`` (public analyzer surface)
and ``trace_flow(cross_module=True)`` on real fixture packages.
"""

from __future__ import annotations

from pathlib import Path

from axm_ast.core.analyzer import analyze_package, find_module_for_symbol
from axm_ast.core.flows import trace_flow
from axm_ast.models.nodes import (
    ModuleInfo,
    PackageInfo,
)


def test_find_source_module_by_dotted_name(tmp_path: Path) -> None:
    """Symbol lookup on a real package returns the owning ModuleInfo."""
    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    core_dir = pkg_dir / "core"
    core_dir.mkdir()
    (core_dir / "__init__.py").write_text("")
    handler_py = core_dir / "handler.py"
    handler_py.write_text("def handle(): pass\n")

    pkg = analyze_package(pkg_dir)
    result = find_module_for_symbol(pkg, "handle")
    assert result is not None
    assert result.path == handler_py.resolve()


class TestCrossModuleEdgeCases:
    """Edge cases for cross-module trace resolution."""

    def test_reexport_missing_target_skipped(self, tmp_path: Path) -> None:
        """An ``__init__`` that re-exports from a missing relative module → the
        broken re-export is silently skipped (no FlowStep, no crash)."""
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        # __init__ tries to re-export Widget from a non-existent ``.missing``
        (pkg_dir / "__init__.py").write_text("from .missing import Widget\n")
        # caller.py imports Widget through the package and uses it
        (pkg_dir / "caller.py").write_text(
            "from pkg import Widget\n\ndef entry():\n    Widget()\n"
        )

        pkg = analyze_package(pkg_dir)
        steps, _ = trace_flow(pkg, "entry", cross_module=True, max_depth=3)
        # Widget never resolves anywhere → no FlowStep for it.
        names = {s.name for s in steps}
        assert "entry" in names
        assert "Widget" not in names


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
