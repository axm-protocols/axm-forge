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
