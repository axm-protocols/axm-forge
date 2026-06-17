"""Unit tests for the axm_ast root package public API."""

from __future__ import annotations

import axm_ast


def test_public_api_exports_analysis_functions() -> None:
    """AC2: the four documented analysis functions are public at root.

    ``find_callers``, ``trace_flow``, ``find_dead_code`` and
    ``structural_diff`` must be re-exported from the package root and
    listed in ``axm_ast.__all__`` (matching the README's public contract).
    """
    expected = ("find_callers", "trace_flow", "find_dead_code", "structural_diff")
    for name in expected:
        assert name in axm_ast.__all__, f"{name} missing from axm_ast.__all__"
        assert hasattr(axm_ast, name), f"{name} not importable from axm_ast"
        assert callable(getattr(axm_ast, name)), f"{name} is not callable"


def test_workspace_symbols_in_all() -> None:
    """AC1: workspace analysis symbols are advertised in ``axm_ast.__all__``."""
    assert "analyze_workspace" in axm_ast.__all__
    assert "build_workspace_module_graph" in axm_ast.__all__


def test_workspace_symbols_top_level_importable() -> None:
    """AC1: workspace analysis symbols are importable from the top level."""
    from axm_ast import analyze_workspace, build_workspace_module_graph

    assert callable(analyze_workspace)
    assert callable(build_workspace_module_graph)
