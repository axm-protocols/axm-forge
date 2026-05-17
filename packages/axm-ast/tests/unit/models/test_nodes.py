"""Unit tests for axm_ast.models.nodes (pure, no I/O)."""

from __future__ import annotations

from pathlib import Path

from axm_ast.models.nodes import ClassInfo, FunctionInfo, ModuleInfo, PackageInfo


def test_public_api_aggregates():
    mod = ModuleInfo(
        path=Path("src/mypkg/core.py"),
        functions=[FunctionInfo(name="run", line_start=1, line_end=1)],
        classes=[ClassInfo(name="Engine", line_start=2, line_end=10)],
    )
    pkg = PackageInfo(name="mypkg", root=Path("src/mypkg"), modules=[mod])
    api = pkg.public_api
    assert len(api) >= 1
