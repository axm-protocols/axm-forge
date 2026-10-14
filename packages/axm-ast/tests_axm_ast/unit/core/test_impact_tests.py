"""Unit tests for the in-memory parts of ``axm_ast.core.impact_tests``."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.impact_tests import (
    MAX_TRANSITIVE_DEPTH,
    ClassHierarchy,
    SymbolTarget,
    validate_transitive_depth,
)
from axm_ast.models.nodes import ClassInfo, ModuleInfo, PackageInfo


def _class(name: str, *bases: str) -> ClassInfo:
    return ClassInfo(name=name, bases=list(bases), line_start=1, line_end=2)


@pytest.fixture
def hierarchy() -> ClassHierarchy:
    """Base <- Mid <- Leaf, plus an unrelated Other and a generic base."""
    module = ModuleInfo(
        path=Path("/demo/mod.py"),
        classes=[
            _class("Base"),
            _class("Mid", "mod.Base"),
            _class("Leaf", "Mid"),
            _class("Other"),
            _class("Typed", "Generic[T]"),
        ],
    )
    return ClassHierarchy(
        PackageInfo(name="demo", root=Path("/demo"), modules=[module])
    )


def test_symbol_target_method_parts() -> None:
    target = SymbolTarget("tools.run", "RunTool.execute")

    assert (target.name, target.owner, target.key) == (
        "execute",
        "RunTool",
        "tools.run.RunTool.execute",
    )


def test_symbol_target_function_has_no_owner() -> None:
    target = SymbolTarget("render", "render_text")

    assert target.owner is None
    assert target.name == "render_text"


def test_descendants_follow_dotted_bases(hierarchy: ClassHierarchy) -> None:
    assert hierarchy.descendants("Base") == {"Base", "Mid", "Leaf"}


def test_family_spans_ancestors_and_descendants(hierarchy: ClassHierarchy) -> None:
    assert hierarchy.family("Mid") == {"Base", "Mid", "Leaf"}
    assert "Other" not in hierarchy.family("Leaf")


def test_generic_bases_are_reduced_to_their_name(hierarchy: ClassHierarchy) -> None:
    assert hierarchy.descendants("Generic") == {"Generic", "Typed"}


@pytest.mark.parametrize("depth", [0, 3, MAX_TRANSITIVE_DEPTH])
def test_validate_transitive_depth_accepts_range(depth: int) -> None:
    validate_transitive_depth(depth)


@pytest.mark.parametrize("depth", [-1, MAX_TRANSITIVE_DEPTH + 1, True])
def test_validate_transitive_depth_rejects_out_of_range(depth: int) -> None:
    with pytest.raises(ValueError, match="transitive_depth"):
        validate_transitive_depth(depth)
