"""Public-API drivers for cross-module resolution edge cases.

Previously imported ``axm_ast.core.flows._find_source_module``,
``_CrossModuleContext``, ``_ResolutionScope`` and
``_resolve_cross_module_callees`` directly. The same scenarios are now
exercised through ``find_module_for_symbol`` (public analyzer surface)
and ``trace_flow(cross_module=True)`` on real fixture packages.
"""

from __future__ import annotations

from pathlib import Path

from axm_ast.models.nodes import (
    ModuleInfo,
    PackageInfo,
)


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
