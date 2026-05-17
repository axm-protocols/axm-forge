"""Unit tests for axm_ast.models (pure, no I/O)."""

from __future__ import annotations

from pathlib import Path

from axm_ast.models import FunctionInfo, ModuleInfo


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


def test_public_functions_with_all_extra():
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
