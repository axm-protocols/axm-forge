"""Integration tests for cst_rewrite file-mutating helpers (real tmp_path I/O)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.cst_rewrite import (
    backfill_missing_imports,
    delete_function_from_source,
    delete_source_if_empty_tests,
    invalidate_import_index,
    patch_file_dunder_depth,
    rename_name_in_module,
    rename_top_level_in_source,
    reorder_module_statements,
    resolve_import_for_symbol,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# patch_file_dunder_depth (subscript + chained .parent forms)
# ---------------------------------------------------------------------------


def test_patch_file_dunder_depth_subscript_form(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text("from pathlib import Path\nROOT = Path(__file__).parents[2]\n")
    msgs = patch_file_dunder_depth(f, depth_delta=1)
    assert "parents[3]" in f.read_text()
    assert any("parents[2] -> parents[3]" in m for m in msgs)


def test_patch_file_dunder_depth_chained_parent_form(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text("ROOT = Path(__file__).parent.parent.parent\n")
    msgs = patch_file_dunder_depth(f, depth_delta=-1)
    text = f.read_text()
    assert text.count(".parent") == 2
    assert any(".parent x3 -> .parent x2" in m for m in msgs)


def test_patch_file_dunder_depth_refuses_subscript_non_positive(
    tmp_path: Path,
) -> None:
    f = tmp_path / "t.py"
    f.write_text("ROOT = Path(__file__).parents[1]\n")
    msgs = patch_file_dunder_depth(f, depth_delta=-2)
    assert "parents[1]" in f.read_text()
    assert any("refusing to patch" in m and "N<=0" in m for m in msgs)


def test_patch_file_dunder_depth_refuses_chain_non_positive(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text("ROOT = Path(__file__).parent.parent\n")
    msgs = patch_file_dunder_depth(f, depth_delta=-3)
    assert f.read_text() == "ROOT = Path(__file__).parent.parent\n"
    assert any("refusing to patch" in m and ".parent" in m for m in msgs)


def test_patch_file_dunder_depth_zero_delta_is_noop(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text("ROOT = Path(__file__).parents[2]\n")
    assert patch_file_dunder_depth(f, depth_delta=0) == []
    assert "parents[2]" in f.read_text()


def test_patch_file_dunder_depth_missing_file_is_noop(tmp_path: Path) -> None:
    f = tmp_path / "absent.py"
    assert patch_file_dunder_depth(f, depth_delta=1) == []


# ---------------------------------------------------------------------------
# rename_name_in_module / rename_top_level_in_source
# ---------------------------------------------------------------------------


def test_rename_name_in_module_rewrites_defs_refs_and_strings(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text(
        '@pytest.mark.usefixtures("old_h")\n'
        "def test_a():\n"
        "    return old_h\n\n"
        "def old_h():\n"
        "    return 1\n"
    )
    rename_name_in_module(f, {"old_h": "new_h"})
    text = f.read_text()
    assert "def new_h(" in text
    assert "return new_h" in text
    assert '"new_h"' in text
    assert "old_h" not in text


def test_rename_name_in_module_renames_classdef(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text("class OldHelper:\n    pass\n\nx = OldHelper\n")
    rename_name_in_module(f, {"OldHelper": "NewHelper"})
    text = f.read_text()
    assert "class NewHelper:" in text
    assert "x = NewHelper" in text


def test_rename_name_in_module_empty_mapping_is_noop(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    original = "def f():\n    pass\n"
    f.write_text(original)
    rename_name_in_module(f, {})
    assert f.read_text() == original


def test_rename_top_level_in_source_renames_header_only(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text("def old_fn():\n    return old_fn\n")
    rename_top_level_in_source(f, {"old_fn": "new_fn"})
    text = f.read_text()
    # Only the def header is renamed; the inner reference is left untouched.
    assert "def new_fn(" in text
    assert "return old_fn" in text


def test_rename_top_level_in_source_empty_mapping_is_noop(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    original = "def keep():\n    pass\n"
    f.write_text(original)
    rename_top_level_in_source(f, {})
    assert f.read_text() == original


# ---------------------------------------------------------------------------
# delete_function_from_source / delete_source_if_empty_tests
# ---------------------------------------------------------------------------


def test_delete_function_from_source_removes_only_target(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text("def a():\n    pass\n\ndef b():\n    pass\n")
    delete_function_from_source(f, "a")
    text = f.read_text()
    assert "def b(" in text
    assert "def a(" not in text


def test_delete_source_if_empty_tests_unlinks_when_no_tests(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text("def helper():\n    return 1\n")
    delete_source_if_empty_tests(f)
    assert not f.exists()


def test_delete_source_if_empty_tests_keeps_file_with_tests(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text("def test_real():\n    assert True\n")
    delete_source_if_empty_tests(f)
    assert f.exists()


def test_delete_source_if_empty_tests_missing_file_is_noop(tmp_path: Path) -> None:
    f = tmp_path / "absent.py"
    delete_source_if_empty_tests(f)
    assert not f.exists()


# ---------------------------------------------------------------------------
# reorder_module_statements
# ---------------------------------------------------------------------------


def test_reorder_module_statements_moves_def_before_use(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text(
        "import pytest\n\n"
        "_skip = pytest.mark.skipif(_tools_available())\n\n"
        "def _tools_available():\n"
        "    return False\n"
    )
    reorder_module_statements(f)
    text = f.read_text()
    # The definition of _tools_available must precede the assignment that uses it.
    assert text.index("def _tools_available") < text.index("_skip = pytest")


def test_reorder_module_statements_already_ordered_is_noop(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    original = (
        "import pytest\n\n"
        "def _tools_available():\n"
        "    return False\n\n"
        "_skip = pytest.mark.skipif(_tools_available())\n"
    )
    f.write_text(original)
    reorder_module_statements(f)
    assert f.read_text() == original


def test_reorder_module_statements_invalid_syntax_is_noop(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    # libcst parses lenient enough but ast.parse fails -> bail, file untouched.
    original = "def (:\n"
    f.write_text(original)
    reorder_module_statements(f)
    assert f.read_text() == original


# ---------------------------------------------------------------------------
# backfill_missing_imports + resolve_import_for_symbol / invalidate
# ---------------------------------------------------------------------------


def test_backfill_missing_imports_copies_from_source(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_text("from pkg import helper\n\n\ndef test_a():\n    helper()\n")
    target = tmp_path / "target.py"
    target.write_text("def test_b():\n    helper()\n")
    msgs = backfill_missing_imports(source, target)
    text = target.read_text()
    assert "from pkg import helper" in text
    assert any("backfilled import for `helper`" in m for m in msgs)


def test_backfill_missing_imports_reports_unresolved(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_text("def test_a():\n    pass\n")
    target = tmp_path / "target.py"
    target.write_text("def test_b():\n    mystery_symbol()\n")
    msgs = backfill_missing_imports(source, target)
    assert any("unresolved import for `mystery_symbol`" in m for m in msgs)


def test_backfill_missing_imports_missing_target_returns_empty(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.py"
    source.write_text("from pkg import helper\n")
    target = tmp_path / "absent.py"
    assert backfill_missing_imports(source, target) == []


def test_backfill_missing_imports_falls_back_to_project_index(
    tmp_path: Path,
) -> None:
    tests_unit = tmp_path / "tests" / "unit"
    tests_unit.mkdir(parents=True)
    (tmp_path / "tests" / "__init__.py").write_text("")
    (tests_unit / "__init__.py").write_text("")
    donor = tests_unit / "test_donor.py"
    donor.write_text("from pkg import shared_helper\n\n\ndef test_x():\n    pass\n")
    source = tmp_path / "source.py"
    source.write_text("def test_a():\n    pass\n")
    target = tmp_path / "target.py"
    target.write_text("def test_b():\n    shared_helper()\n")
    invalidate_import_index(tmp_path)
    msgs = backfill_missing_imports(source, target, project_path=tmp_path)
    assert "from pkg import shared_helper" in target.read_text()
    assert any("backfilled import for `shared_helper`" in m for m in msgs)


def test_resolve_import_for_symbol_finds_top_level_def(tmp_path: Path) -> None:
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "mod.py").write_text("def my_function():\n    return 1\n")
    invalidate_import_index(tmp_path)
    result = resolve_import_for_symbol(tmp_path, "my_function")
    assert result is not None
    stmt, enclosing = result
    import ast

    assert isinstance(stmt, ast.ImportFrom)
    assert stmt.module == "mypkg.mod"
    assert enclosing is None


def test_resolve_import_for_symbol_unknown_returns_none(tmp_path: Path) -> None:
    (tmp_path / "mod.py").write_text("x = 1\n")
    invalidate_import_index(tmp_path)
    assert resolve_import_for_symbol(tmp_path, "no_such_symbol") is None


def test_backfill_missing_imports_synthesizes_from_helpers(tmp_path: Path) -> None:
    """A name defined only in ``tests/<tier>/_helpers.py`` is synthesised."""
    tests_unit = tmp_path / "tests" / "unit"
    tests_unit.mkdir(parents=True)
    (tmp_path / "tests" / "__init__.py").write_text("")
    (tests_unit / "__init__.py").write_text("")
    (tests_unit / "_helpers.py").write_text("def make_widget():\n    return 1\n")
    source = tmp_path / "source.py"
    source.write_text("def test_a():\n    pass\n")
    target = tmp_path / "target.py"
    target.write_text("def test_b():\n    make_widget()\n")
    invalidate_import_index(tmp_path)
    msgs = backfill_missing_imports(source, target, project_path=tmp_path)
    assert "import make_widget" in target.read_text()
    assert any("backfilled import for `make_widget`" in m for m in msgs)


def test_backfill_missing_imports_into_type_checking_block(tmp_path: Path) -> None:
    """A donor import living in a ``if TYPE_CHECKING:`` block is replayed there."""
    source = tmp_path / "source.py"
    source.write_text(
        "from typing import TYPE_CHECKING\n\n"
        "if TYPE_CHECKING:\n"
        "    from pkg import Widget\n"
    )
    target = tmp_path / "target.py"
    target.write_text("def test_b(obj: Widget) -> None:\n    assert obj\n")
    msgs = backfill_missing_imports(source, target)
    text = target.read_text()
    assert "if TYPE_CHECKING:" in text
    assert "from pkg import Widget" in text
    assert any("backfilled import for `Widget`" in m for m in msgs)
