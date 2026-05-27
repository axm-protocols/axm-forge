"""Unit tests for axm_audit.core.fix.cst_rewrite — CST mutation layer."""

from __future__ import annotations

import textwrap
from collections.abc import Callable

import libcst as cst


def _rewrite_and_dump(src: str, rewriter_fn: Callable[[cst.Module], cst.Module]) -> str:
    """Parse *src*, run *rewriter_fn* on the module, return rendered code."""
    module = cst.parse_module(textwrap.dedent(src).lstrip("\n"))
    rewritten = rewriter_fn(module)
    if isinstance(rewritten, cst.Module):
        return rewritten.code
    return str(rewritten)


# ---------------------------------------------------------------------------
# AC1 — flatten class to top-level functions
# ---------------------------------------------------------------------------


def test_flatten_class_to_top_level_funcs() -> None:
    """AC1: class-flatten rewriter turns methods into top-level functions."""
    from axm_audit.core.fix.cst_rewrite import flatten_class

    src = """
        class TestX:
            def test_a(self):
                assert 1

            def test_b(self):
                assert 2
    """
    result = _rewrite_and_dump(src, lambda m: flatten_class(m, "TestX"))
    assert "def test_a(" in result
    assert "def test_b(" in result
    assert "class TestX" not in result


def test_flatten_preserves_method_decorators() -> None:
    """AC1: decorators on flattened methods survive the rewrite."""
    from axm_audit.core.fix.cst_rewrite import flatten_class

    src = """
        import pytest

        class TestX:
            @pytest.mark.skip
            def test_a(self):
                assert 1
    """
    result = _rewrite_and_dump(src, lambda m: flatten_class(m, "TestX"))
    assert "@pytest.mark.skip" in result
    assert "def test_a(" in result
    assert "class TestX" not in result


# ---------------------------------------------------------------------------
# AC2 — rename top-level function
# ---------------------------------------------------------------------------


def test_rename_function() -> None:
    """AC2: rename rewriter changes the function name in-place."""
    from axm_audit.core.fix.cst_rewrite import rename_function

    src = "def test_old():\n    pass\n"
    result = _rewrite_and_dump(
        src, lambda m: rename_function(m, "test_old", "test_new")
    )
    assert "def test_new(" in result
    assert "test_old" not in result


# ---------------------------------------------------------------------------
# AC3 — delete top-level function, preserve neighbours
# ---------------------------------------------------------------------------


def test_delete_top_level_function_preserves_neighbors() -> None:
    """AC3: delete rewriter removes target and leaves siblings untouched."""
    from axm_audit.core.fix.cst_rewrite import delete_function

    src = """
        def f_a():
            pass

        def f_b():
            pass

        def f_c():
            pass
    """
    result = _rewrite_and_dump(src, lambda m: delete_function(m, "f_b"))
    assert "def f_a(" in result
    assert "def f_c(" in result
    assert "def f_b(" not in result
    # No triple-blank gap where f_b used to be.
    assert "\n\n\n\n" not in result


# ---------------------------------------------------------------------------
# AC4 — Path(__file__).parents[N] depth patch
# ---------------------------------------------------------------------------


def test_depth_patch_increments_parents_index() -> None:
    """AC4: depth_delta=+1 increments the parents[N] integer literal."""
    from axm_audit.core.fix.cst_rewrite import patch_file_depth

    src = "from pathlib import Path\nROOT = Path(__file__).parents[2]\n"
    result = _rewrite_and_dump(src, lambda m: patch_file_depth(m, depth_delta=1))
    assert "parents[3]" in result
    assert "parents[2]" not in result


def test_depth_patch_zero_delta_is_identity() -> None:
    """AC4: depth_delta=0 leaves the source unchanged."""
    from axm_audit.core.fix.cst_rewrite import patch_file_depth

    src = "from pathlib import Path\nROOT = Path(__file__).parents[2]\n"
    result = _rewrite_and_dump(src, lambda m: patch_file_depth(m, depth_delta=0))
    assert "parents[2]" in result
    assert "parents[3]" not in result


def test_depth_patch_absent_pattern_noop() -> None:
    """AC4: when the parents[N] pattern is missing, the source is unchanged."""
    from axm_audit.core.fix.cst_rewrite import patch_file_depth

    src = "x = 42\n"
    result = _rewrite_and_dump(src, lambda m: patch_file_depth(m, depth_delta=1))
    assert result.strip() == "x = 42"


# ---------------------------------------------------------------------------
# AC5 — dedupe duplicate imports
# ---------------------------------------------------------------------------


def test_imports_dedupe_collapses_duplicates() -> None:
    """AC5: dedupe rewriter collapses `import os` repeated twice into one."""
    from axm_audit.core.fix.cst_rewrite import dedupe_imports

    src = """
        import os
        import sys
        import os
    """
    result = _rewrite_and_dump(src, lambda m: dedupe_imports(m))
    # Count standalone `import os` lines (not substring of other tokens).
    lines = [line.strip() for line in result.splitlines()]
    assert lines.count("import os") == 1
    assert lines.count("import sys") == 1


# ---------------------------------------------------------------------------
# AC6 — backfill missing imports at canonical position
# ---------------------------------------------------------------------------


def test_imports_backfill_inserts_after_future() -> None:
    """AC6: backfill inserts new import after __future__, before first stmt."""
    from axm_audit.core.fix.cst_rewrite import backfill_import

    src = """
        from __future__ import annotations

        def f():
            foo()
    """
    result = _rewrite_and_dump(src, lambda m: backfill_import(m, {"foo": "pkg"}))
    future_idx = result.find("from __future__")
    new_idx = result.find("from pkg import foo")
    def_idx = result.find("def f")
    assert future_idx >= 0
    assert new_idx >= 0
    assert def_idx >= 0
    assert future_idx < new_idx < def_idx


def test_imports_backfill_no_future_inserts_at_top() -> None:
    """AC6: with no __future__ import, backfill inserts at module top."""
    from axm_audit.core.fix.cst_rewrite import backfill_import

    src = """
        def f():
            foo()
    """
    result = _rewrite_and_dump(src, lambda m: backfill_import(m, {"foo": "pkg"}))
    new_idx = result.find("from pkg import foo")
    def_idx = result.find("def f")
    assert new_idx >= 0
    assert def_idx >= 0
    assert new_idx < def_idx
