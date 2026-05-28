"""Unit tests for axm_audit.core.fix.stages_execute CST helpers + dispatch."""

from __future__ import annotations

import ast
from pathlib import Path

import libcst as cst

from axm_audit.core.fix.stages_execute import (
    _collect_fixture_closure,
    _cst_annassign_target_name,
    _cst_assign_target_names,
    _cst_names_in_node,
    _cst_simple_stmt_names,
    _cst_stmt_defines_name,
    _index_top_level_stmts,
    _is_copyable_dep_stmt,
    _ordered_copy_stmts,
    _split_pathological_leftover,
    execute,
)


def _parse_cst(src: str) -> cst.Module:
    return cst.parse_module(src)


# ---------------------------------------------------------------------------
# CST name extraction helpers
# ---------------------------------------------------------------------------


def test_cst_assign_target_names_simple_and_tuple() -> None:
    """_cst_assign_target_names extracts all top-level cst.Name targets."""
    module = _parse_cst("FOO = 1\nBAR = BAZ = 2\n")
    foo_assign = module.body[0].body[0]
    assert isinstance(foo_assign, cst.Assign)
    assert _cst_assign_target_names(foo_assign) == ["FOO"]
    multi_assign = module.body[1].body[0]
    assert isinstance(multi_assign, cst.Assign)
    assert _cst_assign_target_names(multi_assign) == ["BAR", "BAZ"]


def test_cst_annassign_target_name_returns_name() -> None:
    """_cst_annassign_target_name returns the annotated target name."""
    module = _parse_cst("X: int = 1\n")
    ann = module.body[0].body[0]
    assert isinstance(ann, cst.AnnAssign)
    assert _cst_annassign_target_name(ann) == "X"


def test_cst_simple_stmt_names_combines_assign_and_annassign() -> None:
    """_cst_simple_stmt_names gathers names from Assign and AnnAssign lines."""
    module = _parse_cst("FOO = 1\nBAR: int = 2\n")
    foo = module.body[0]
    assert isinstance(foo, cst.SimpleStatementLine)
    bar = module.body[1]
    assert isinstance(bar, cst.SimpleStatementLine)
    assert _cst_simple_stmt_names(foo) == ["FOO"]
    assert _cst_simple_stmt_names(bar) == ["BAR"]


def test_cst_stmt_defines_name_function_class_assign() -> None:
    """_cst_stmt_defines_name matches function defs, class defs, and assigns."""
    module = _parse_cst("def f(): pass\nclass C: pass\nFOO = 1\nimport sys\n")
    fn, cls, assign, importer = module.body
    assert _cst_stmt_defines_name(fn, "f") is True
    assert _cst_stmt_defines_name(fn, "g") is False
    assert _cst_stmt_defines_name(cls, "C") is True
    assert _cst_stmt_defines_name(assign, "FOO") is True
    assert _cst_stmt_defines_name(assign, "BAR") is False
    # ``import sys`` is a SimpleStatementLine that does not Assign — it
    # defines no Assign/AnnAssign target.
    assert _cst_stmt_defines_name(importer, "sys") is False


def test_cst_names_in_node_collects_all_name_references() -> None:
    """_cst_names_in_node walks every cst.Name under the node."""
    module = _parse_cst("def f():\n    return a + b + c\n")
    fn = module.body[0]
    assert isinstance(fn, cst.FunctionDef)
    names = _cst_names_in_node(fn)
    assert {"a", "b", "c", "f"} <= names


# ---------------------------------------------------------------------------
# Copyability + indexing
# ---------------------------------------------------------------------------


def test_is_copyable_dep_stmt_simple_stmt_and_helper_def() -> None:
    """Simple statements and non-test FunctionDef are copyable; tests aren't."""
    module = _parse_cst(
        "FOO = 1\ndef helper(): pass\ndef test_x(): pass\nclass C: pass\n"
    )
    assign, helper, test_fn, klass = module.body
    assert _is_copyable_dep_stmt(assign) is True
    assert _is_copyable_dep_stmt(helper) is True
    assert _is_copyable_dep_stmt(test_fn) is False
    assert _is_copyable_dep_stmt(klass) is False


def test_index_top_level_stmts_maps_each_name() -> None:
    """_index_top_level_stmts maps each defined name to its statement."""
    module = _parse_cst("FOO = 1\nclass C: pass\ndef f(): pass\n")
    idx = _index_top_level_stmts(module)
    assert set(idx) == {"FOO", "C", "f"}


# ---------------------------------------------------------------------------
# Fixture closure + ordered copy
# ---------------------------------------------------------------------------


def test_collect_fixture_closure_pulls_transitive_helpers() -> None:
    """_collect_fixture_closure BFS-walks transitively referenced helpers."""
    module = _parse_cst(
        "def helper_a(): pass\ndef helper_b():\n    return helper_a()\n"
        "def fx():\n    return helper_b()\n"
    )
    by_name = _index_top_level_stmts(module)
    to_copy = _collect_fixture_closure("fx", by_name, anchor_defined=set())
    assert to_copy == {"fx", "helper_a", "helper_b"}


def test_collect_fixture_closure_stops_at_anchor_defined() -> None:
    """Names already present in the anchor are not copied again."""
    module = _parse_cst("def helper_a(): pass\ndef fx():\n    return helper_a()\n")
    by_name = _index_top_level_stmts(module)
    to_copy = _collect_fixture_closure("fx", by_name, anchor_defined={"helper_a"})
    assert to_copy == {"fx"}


def test_collect_fixture_closure_missing_root_returns_just_root() -> None:
    """When the root is not in the index, the closure is just {root}."""
    by_name: dict[str, cst.BaseStatement] = {}
    assert _collect_fixture_closure("ghost", by_name, set()) == {"ghost"}


def test_ordered_copy_stmts_preserves_source_order() -> None:
    """_ordered_copy_stmts emits (name, stmt) in original source order."""
    module = _parse_cst("def first(): pass\ndef second(): pass\ndef third(): pass\n")
    out = _ordered_copy_stmts(module, {"third", "first"})
    names = [name for name, _ in out]
    assert names == ["first", "third"]


# ---------------------------------------------------------------------------
# execute() with empty input + _split_pathological_leftover
# ---------------------------------------------------------------------------


def test_execute_with_no_ops_returns_empty(tmp_path: Path) -> None:
    """execute([]) is a safe no-op."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\nversion="0"\n')
    (tmp_path / "src" / "x").mkdir(parents=True)
    (tmp_path / "src" / "x" / "__init__.py").write_text("")
    assert execute([], tmp_path) == []


def test_split_pathological_leftover_returns_empty_when_no_classes(
    tmp_path: Path,
) -> None:
    """_split_pathological_leftover returns [] when no Test* classes exist."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\nversion="0"\n')
    (tmp_path / "src" / "x").mkdir(parents=True)
    (tmp_path / "src" / "x" / "__init__.py").write_text("")
    tree = ast.parse("def test_x(): pass\n")
    assert _split_pathological_leftover(tree, "integration", tmp_path) == []
