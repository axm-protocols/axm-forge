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


def test_imports_backfill_empty_mapping_is_identity() -> None:
    """AC6: empty mapping returns the input module untouched."""
    from axm_audit.core.fix.cst_rewrite import backfill_import

    src = "x = 1\n"
    result = _rewrite_and_dump(src, lambda m: backfill_import(m, {}))
    assert result == "x = 1\n"


def test_imports_backfill_already_imported_skipped() -> None:
    """AC6: names already imported in the module are not re-inserted."""
    from axm_audit.core.fix.cst_rewrite import backfill_import

    src = "from pkg import foo\n\nfoo()\n"
    result = _rewrite_and_dump(src, lambda m: backfill_import(m, {"foo": "pkg"}))
    assert result.count("from pkg import foo") == 1


def test_imports_backfill_dotted_module_path() -> None:
    """AC6: backfill supports dotted module paths via _dotted_name_to_cst."""
    from axm_audit.core.fix.cst_rewrite import backfill_import

    src = "def f():\n    helper()\n"
    result = _rewrite_and_dump(src, lambda m: backfill_import(m, {"helper": "a.b.c"}))
    assert "from a.b.c import helper" in result


# ---------------------------------------------------------------------------
# dedupe_imports — additional scenarios
# ---------------------------------------------------------------------------


def test_dedupe_imports_from_module_collapses_repeat() -> None:
    """Same ``from X import Y`` repeated twice is collapsed."""
    from axm_audit.core.fix.cst_rewrite import dedupe_imports

    src = "from pkg import foo\nfrom pkg import foo\nfrom pkg import bar\n"
    result = _rewrite_and_dump(src, lambda m: dedupe_imports(m))
    lines = [line for line in result.splitlines() if line.strip()]
    assert lines.count("from pkg import foo") == 1
    assert lines.count("from pkg import bar") == 1


def test_dedupe_imports_shadow_drops_later_binding() -> None:
    """When two imports both bind ``X`` locally, the first import wins."""
    from axm_audit.core.fix.cst_rewrite import dedupe_imports

    src = "from a import X\nfrom a.b import X\n"
    result = _rewrite_and_dump(src, lambda m: dedupe_imports(m))
    # The shadow rule keeps the first binding only.
    assert "from a import X" in result
    assert "from a.b import X" not in result


def test_dedupe_imports_leaves_non_import_statements() -> None:
    """Non-import top-level statements are preserved unchanged."""
    from axm_audit.core.fix.cst_rewrite import dedupe_imports

    src = "import os\nimport os\nx = 1\n\ndef f(): pass\n"
    result = _rewrite_and_dump(src, lambda m: dedupe_imports(m))
    assert "x = 1" in result
    assert "def f(" in result


# ---------------------------------------------------------------------------
# patch_file_depth — negative delta
# ---------------------------------------------------------------------------


def test_depth_patch_negative_delta_decrements_parents_index() -> None:
    """AC4: depth_delta=-1 decrements the parents[N] integer literal."""
    from axm_audit.core.fix.cst_rewrite import patch_file_depth

    src = "from pathlib import Path\nROOT = Path(__file__).parents[3]\n"
    result = _rewrite_and_dump(src, lambda m: patch_file_depth(m, depth_delta=-1))
    assert "parents[2]" in result
    assert "parents[3]" not in result


# ---------------------------------------------------------------------------
# flatten_class — additional scenarios
# ---------------------------------------------------------------------------


def test_flatten_class_with_no_decorators_keeps_methods() -> None:
    """Class without decorators still flattens to top-level functions."""
    from axm_audit.core.fix.cst_rewrite import flatten_class

    src = "class TestX:\n    def test_one(self):\n        return 1\n"
    result = _rewrite_and_dump(src, lambda m: flatten_class(m, "TestX"))
    assert "def test_one(" in result
    assert "class TestX" not in result


def test_flatten_class_unknown_name_is_noop() -> None:
    """Asking to flatten a class not present in source is a no-op."""
    from axm_audit.core.fix.cst_rewrite import flatten_class

    src = "class TestX:\n    def test_a(self): pass\n"
    result = _rewrite_and_dump(src, lambda m: flatten_class(m, "TestY"))
    assert "class TestX" in result


# ---------------------------------------------------------------------------
# rename_function / delete_function — extra branches
# ---------------------------------------------------------------------------


def test_rename_function_absent_name_is_noop() -> None:
    """Renaming a function that doesn't exist returns the module unchanged."""
    from axm_audit.core.fix.cst_rewrite import rename_function

    src = "def f(): pass\n"
    result = _rewrite_and_dump(src, lambda m: rename_function(m, "g_absent", "h_new"))
    assert "def f(" in result
    assert "h_new" not in result


def test_delete_function_absent_is_noop() -> None:
    """Deleting a function that doesn't exist leaves the module unchanged."""
    from axm_audit.core.fix.cst_rewrite import delete_function

    src = "def keep(): pass\n"
    result = _rewrite_and_dump(src, lambda m: delete_function(m, "absent"))
    assert "def keep(" in result


# ---------------------------------------------------------------------------
# flatten_class — docstring / fixture / mark propagation branches
# ---------------------------------------------------------------------------


def test_flatten_class_drops_class_docstring() -> None:
    """The class docstring (a SimpleString Expr) is dropped on flatten."""
    from axm_audit.core.fix.cst_rewrite import flatten_class

    src = '''
        class TestX:
            """This is the class docstring."""

            def test_a(self):
                assert 1
    '''
    result = _rewrite_and_dump(src, lambda m: flatten_class(m, "TestX"))
    assert "This is the class docstring." not in result
    assert "def test_a(" in result


def test_flatten_class_strips_self_param() -> None:
    """The leading ``self`` param is dropped from promoted methods."""
    from axm_audit.core.fix.cst_rewrite import flatten_class

    src = "class TestX:\n    def test_a(self, value):\n        assert value\n"
    result = _rewrite_and_dump(src, lambda m: flatten_class(m, "TestX"))
    assert "def test_a(value)" in result
    assert "self" not in result


def test_flatten_class_propagates_class_pytest_mark() -> None:
    """A class-level ``@pytest.mark.*`` mark lands on each promoted test."""
    from axm_audit.core.fix.cst_rewrite import flatten_class

    src = """
        import pytest

        @pytest.mark.integration
        class TestX:
            def test_a(self):
                assert 1

            def test_b(self):
                assert 2
    """
    result = _rewrite_and_dump(src, lambda m: flatten_class(m, "TestX"))
    assert result.count("@pytest.mark.integration") == 2
    assert "class TestX" not in result


def test_flatten_class_drops_non_pytest_class_decorator() -> None:
    """A non-``pytest.mark`` class decorator is dropped, not propagated."""
    from axm_audit.core.fix.cst_rewrite import flatten_class

    src = """
        @some_adapter
        class TestX:
            def test_a(self):
                assert 1
    """
    result = _rewrite_and_dump(src, lambda m: flatten_class(m, "TestX"))
    assert "@some_adapter" not in result
    assert "def test_a(" in result


def test_flatten_class_promotes_helper_without_self() -> None:
    """A helper method without ``self`` is promoted verbatim (no param strip)."""
    from axm_audit.core.fix.cst_rewrite import flatten_class

    src = """
        class TestX:
            def _helper(value):
                return value * 2

            def test_a(self):
                assert _helper(2) == 4
    """
    result = _rewrite_and_dump(src, lambda m: flatten_class(m, "TestX"))
    assert "def _helper(value)" in result
    assert "class TestX" not in result


def test_flatten_class_promotes_class_level_assignment() -> None:
    """A non-function class child (assignment) is promoted to top level."""
    from axm_audit.core.fix.cst_rewrite import flatten_class

    src = """
        class TestX:
            CONST = 5

            def test_a(self):
                assert TestX
    """
    result = _rewrite_and_dump(src, lambda m: flatten_class(m, "TestX"))
    assert "CONST = 5" in result


# ---------------------------------------------------------------------------
# rename_function — Name reference + marker-string rewrite
# ---------------------------------------------------------------------------


def test_rename_function_rewrites_name_references() -> None:
    """Every ``Name`` reference to the old function is rewritten too."""
    from axm_audit.core.fix.cst_rewrite import rename_function

    src = "def test_old():\n    pass\n\nrunner = test_old\n"
    result = _rewrite_and_dump(
        src, lambda m: rename_function(m, "test_old", "test_new")
    )
    assert "runner = test_new" in result
    assert "test_old" not in result


def test_rename_function_rewrites_marker_string_literal() -> None:
    """A matching string literal (e.g. parametrize id) is rewritten."""
    from axm_audit.core.fix.cst_rewrite import rename_function

    src = '@pytest.mark.usefixtures("old_fix")\ndef test_a():\n    pass\n'
    result = _rewrite_and_dump(src, lambda m: rename_function(m, "old_fix", "new_fix"))
    assert '"new_fix"' in result
    assert "old_fix" not in result


def test_rename_function_ignores_non_matching_string() -> None:
    """String literals that don't match the old name are left intact."""
    from axm_audit.core.fix.cst_rewrite import rename_function

    src = 'def test_old():\n    msg = "unrelated literal"\n    return msg\n'
    result = _rewrite_and_dump(
        src, lambda m: rename_function(m, "test_old", "test_new")
    )
    assert '"unrelated literal"' in result
    assert "def test_new(" in result


# ---------------------------------------------------------------------------
# patch_file_depth — guard branches and refuse-to-patch
# ---------------------------------------------------------------------------


def test_patch_file_depth_refuses_when_result_non_positive() -> None:
    """depth_delta that would make N<=0 leaves the literal unchanged."""
    from axm_audit.core.fix.cst_rewrite import patch_file_depth

    src = "from pathlib import Path\nROOT = Path(__file__).parents[1]\n"
    result = _rewrite_and_dump(src, lambda m: patch_file_depth(m, depth_delta=-1))
    assert "parents[1]" in result
    assert "parents[0]" not in result


def test_patch_file_depth_ignores_non_parents_subscript() -> None:
    """A subscript on a non-``parents`` attribute is left alone."""
    from axm_audit.core.fix.cst_rewrite import patch_file_depth

    src = "data = obj.items[2]\n"
    result = _rewrite_and_dump(src, lambda m: patch_file_depth(m, depth_delta=1))
    assert "obj.items[2]" in result


def test_patch_file_depth_ignores_non_file_dunder_parents() -> None:
    """``something.parents[N]`` not rooted at ``Path(__file__)`` is skipped."""
    from axm_audit.core.fix.cst_rewrite import patch_file_depth

    src = "ROOT = some_path.parents[2]\n"
    result = _rewrite_and_dump(src, lambda m: patch_file_depth(m, depth_delta=1))
    assert "some_path.parents[2]" in result


def test_patch_file_depth_handles_resolve_wrapper() -> None:
    """``Path(__file__).resolve().parents[N]`` is still recognised and patched."""
    from axm_audit.core.fix.cst_rewrite import patch_file_depth

    src = "ROOT = Path(__file__).resolve().parents[2]\n"
    result = _rewrite_and_dump(src, lambda m: patch_file_depth(m, depth_delta=1))
    assert "parents[3]" in result
    assert "parents[2]" not in result


# ---------------------------------------------------------------------------
# dedupe_imports — star imports + TYPE_CHECKING block dedup
# ---------------------------------------------------------------------------


def test_dedupe_imports_preserves_star_import() -> None:
    """``from x import *`` is never collapsed (no per-alias bindings)."""
    from axm_audit.core.fix.cst_rewrite import dedupe_imports

    src = "from pkg import *\nfrom pkg import *\n"
    result = _rewrite_and_dump(src, lambda m: dedupe_imports(m))
    assert result.count("from pkg import *") == 2


def test_dedupe_imports_dedupes_inside_type_checking_block() -> None:
    """Duplicate imports inside ``if TYPE_CHECKING:`` are collapsed."""
    from axm_audit.core.fix.cst_rewrite import dedupe_imports

    src = """
        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            from pkg import Foo
            from pkg import Foo
    """
    result = _rewrite_and_dump(src, lambda m: dedupe_imports(m))
    assert result.count("from pkg import Foo") == 1


def test_dedupe_imports_drops_emptied_type_checking_block() -> None:
    """A TYPE_CHECKING block emptied by dedup is removed entirely."""
    from axm_audit.core.fix.cst_rewrite import dedupe_imports

    src = """
        from pkg import Foo

        if TYPE_CHECKING:
            from pkg import Foo
    """
    result = _rewrite_and_dump(src, lambda m: dedupe_imports(m))
    assert result.count("from pkg import Foo") == 1
    assert "if TYPE_CHECKING:" not in result


# ---------------------------------------------------------------------------
# patch_file_depth — subscript guard branches (non-index / non-integer)
# ---------------------------------------------------------------------------


def test_patch_file_depth_ignores_slice_index() -> None:
    """A slice (``parents[1:2]``) is not an Index literal, so it's skipped."""
    from axm_audit.core.fix.cst_rewrite import patch_file_depth

    src = "ROOT = Path(__file__).parents[1:2]\n"
    result = _rewrite_and_dump(src, lambda m: patch_file_depth(m, depth_delta=1))
    assert "parents[1:2]" in result


def test_patch_file_depth_ignores_non_integer_index() -> None:
    """A non-integer index (``parents[n]``) is left unchanged."""
    from axm_audit.core.fix.cst_rewrite import patch_file_depth

    src = "ROOT = Path(__file__).parents[n]\n"
    result = _rewrite_and_dump(src, lambda m: patch_file_depth(m, depth_delta=1))
    assert "parents[n]" in result
