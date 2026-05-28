"""Unit tests for axm_audit.core.fix.layout_and_move read-only helpers."""

from __future__ import annotations

import ast
from pathlib import Path

from axm_audit.core.fix.layout_and_move import (
    _bounded_rename,
    _camel_from_snake,
    _index_top_level_defs,
    _iter_non_canonical_tier_dirs,
    _names_segment,
    _prune_empty_test_subdirs,
    _resolve_flatten_target,
    _rewrite_file_imports,
    _subdir_has_test_file,
    _top_class_names,
    _top_def_names,
    _top_test_funcs,
    _trailing_comment,
    _unique_integration_target,
)

# ---------------------------------------------------------------------------
# String / AST pure helpers
# ---------------------------------------------------------------------------


def test_camel_from_snake_prepends_from_and_capitalizes() -> None:
    """_camel_from_snake makes ``hello_world`` -> ``FromHelloWorld``."""
    assert _camel_from_snake("hello_world") == "FromHelloWorld"
    assert _camel_from_snake("single") == "FromSingle"
    assert _camel_from_snake("") == "From"


def test_bounded_rename_under_max_keeps_full_suffix() -> None:
    """Short names use the full ``name + suffix`` form."""
    assert _bounded_rename("foo", "__from_bar", "bar") == "foo__from_bar"


def test_bounded_rename_uses_hash_when_too_long() -> None:
    """Long stems trigger a sha1-shortened ``__from_<digest>`` suffix."""
    long_name = "x" * 70
    long_suffix = "__from_some_very_long_stem_name_here_extra_padding"
    out = _bounded_rename(long_name, long_suffix, "my_stem")
    # Must include the digest pattern, not the original suffix.
    assert "__from_" in out
    assert long_suffix not in out
    assert len(out) <= 73


def test_bounded_rename_truncates_head_when_even_short_suffix_overflows() -> None:
    """When name + short_suffix still overflows, the head is truncated."""
    name = "a" * 80
    out = _bounded_rename(name, "__from_xyz", "stem")
    assert len(out) <= 73
    assert "__from_" in out


def test_names_segment_handles_aliases() -> None:
    """``import x, y as z`` renders as ``x, y as z``."""
    node = ast.parse("from m import x, y as z\n").body[0]
    assert isinstance(node, ast.ImportFrom)
    assert _names_segment(node) == "x, y as z"


def test_names_segment_single_plain_import() -> None:
    node = ast.parse("from m import a\n").body[0]
    assert isinstance(node, ast.ImportFrom)
    assert _names_segment(node) == "a"


def test_trailing_comment_returns_inline_hash() -> None:
    """_trailing_comment extracts inline comments preceded by ``  ``."""
    text_lines = ["x = 1  # keep this"]
    assert _trailing_comment(text_lines, 1) == "  # keep this"


def test_trailing_comment_returns_empty_when_no_hash() -> None:
    assert _trailing_comment(["x = 1"], 1) == ""


def test_trailing_comment_returns_empty_on_out_of_range() -> None:
    assert _trailing_comment([], 1) == ""
    assert _trailing_comment(["x"], 0) == ""
    assert _trailing_comment(["x"], 5) == ""


# ---------------------------------------------------------------------------
# AST top-level scans
# ---------------------------------------------------------------------------


def test_top_def_names_collects_classes_and_functions() -> None:
    tree = ast.parse("def f(): pass\nclass C: pass\nx = 1\n")
    assert _top_def_names(tree) == {"f", "C"}


def test_top_class_names_filters_to_classdef() -> None:
    tree = ast.parse("def f(): pass\nclass C: pass\nclass D: pass\n")
    assert _top_class_names(tree) == {"C", "D"}


def test_top_test_funcs_filters_by_prefix() -> None:
    tree = ast.parse("def test_a(): pass\ndef helper(): pass\ndef test_b(): pass\n")
    funcs = _top_test_funcs(tree)
    assert set(funcs) == {"test_a", "test_b"}


def test_index_top_level_defs_excludes_non_def() -> None:
    tree = ast.parse("def f(): pass\nclass C: pass\nx = 1\n")
    idx = _index_top_level_defs(tree)
    assert set(idx) == {"f", "C"}
    assert idx["f"].name == "f"
    assert idx["C"].name == "C"


# ---------------------------------------------------------------------------
# Filesystem helpers (use tmp_path, no git)
# ---------------------------------------------------------------------------


def test_subdir_has_test_file_true_when_present(tmp_path: Path) -> None:
    (tmp_path / "test_x.py").write_text("")
    assert _subdir_has_test_file(tmp_path) is True


def test_subdir_has_test_file_false_for_only_scaffolding(tmp_path: Path) -> None:
    (tmp_path / "__init__.py").write_text("")
    (tmp_path / "conftest.py").write_text("")
    assert _subdir_has_test_file(tmp_path) is False


def test_subdir_has_test_file_false_when_empty(tmp_path: Path) -> None:
    assert _subdir_has_test_file(tmp_path) is False


def test_prune_empty_test_subdirs_removes_scaffolding_only_dirs(tmp_path: Path) -> None:
    """Subdir with only __init__.py / conftest.py is pruned."""
    tier = tmp_path / "integration"
    tier.mkdir()
    empty_sub = tier / "hooks"
    empty_sub.mkdir()
    (empty_sub / "__init__.py").write_text("")
    (empty_sub / "conftest.py").write_text("")
    _prune_empty_test_subdirs(tier)
    assert not empty_sub.exists()
    assert tier.exists()


def test_prune_empty_test_subdirs_keeps_subdir_with_tests(tmp_path: Path) -> None:
    tier = tmp_path / "integration"
    tier.mkdir()
    live_sub = tier / "hooks"
    live_sub.mkdir()
    (live_sub / "test_keep.py").write_text("")
    _prune_empty_test_subdirs(tier)
    assert live_sub.exists()
    assert (live_sub / "test_keep.py").exists()


def test_unique_integration_target_no_collision(tmp_path: Path) -> None:
    """When the target doesn't exist, return it as-is."""
    src = tmp_path / "functional" / "test_x.py"
    src.parent.mkdir()
    src.write_text("")
    integration = tmp_path / "integration"
    integration.mkdir()
    target = _unique_integration_target(src, integration)
    assert target == integration / "test_x.py"


def test_unique_integration_target_disambiguates_collision(tmp_path: Path) -> None:
    """When the target already exists, suffix ``_2`` is appended."""
    src = tmp_path / "functional" / "test_x.py"
    src.parent.mkdir()
    src.write_text("")
    integration = tmp_path / "integration"
    integration.mkdir()
    (integration / "test_x.py").write_text("collision")
    target = _unique_integration_target(src, integration)
    assert target == integration / "test_x_2.py"


def test_iter_non_canonical_tier_dirs_returns_non_canonical(tmp_path: Path) -> None:
    """Returns only non-canonical, non-fixture, non-hidden test subdirs."""
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "unit").mkdir()
    (tests / "integration").mkdir()
    (tests / "e2e").mkdir()
    (tests / "fixtures").mkdir()
    (tests / "_helpers").mkdir()
    (tests / ".hidden").mkdir()
    (tests / "functional").mkdir()
    (tests / "perf").mkdir()
    out = {p.name for p in _iter_non_canonical_tier_dirs(tests)}
    assert out == {"functional", "perf"}


def test_resolve_flatten_target_no_collision(tmp_path: Path) -> None:
    """When the flattened target doesn't exist, return it."""
    tier = tmp_path / "integration"
    sub = tier / "hooks"
    sub.mkdir(parents=True)
    src = sub / "test_x.py"
    src.write_text("")
    target = _resolve_flatten_target(src, tier)
    assert target == tier / "test_x.py"


def test_resolve_flatten_target_disambiguates_with_subpath_prefix(
    tmp_path: Path,
) -> None:
    """On collision, prefix with the source's relative dir parts."""
    tier = tmp_path / "integration"
    sub = tier / "hooks"
    sub.mkdir(parents=True)
    src = sub / "test_x.py"
    src.write_text("")
    (tier / "test_x.py").write_text("collision")
    target = _resolve_flatten_target(src, tier)
    assert target.name == "test_hooks_x.py"


def test_rewrite_file_imports_substitutes_old_module(tmp_path: Path) -> None:
    """_rewrite_file_imports rewrites ``from old import X`` to one new module."""
    py = tmp_path / "test_a.py"
    py.write_text("from old.mod import helper\n\nhelper()\n")
    changed = _rewrite_file_imports(py, "old.mod", ["new.mod"])
    assert changed is True
    rewritten = py.read_text()
    assert "from new.mod import helper" in rewritten
    assert "old.mod" not in rewritten


def test_rewrite_file_imports_returns_false_when_module_absent(tmp_path: Path) -> None:
    """No-op when the old module is not mentioned."""
    py = tmp_path / "test_a.py"
    py.write_text("from unrelated import x\n")
    assert _rewrite_file_imports(py, "old.mod", ["new.mod"]) is False


def test_rewrite_file_imports_returns_false_on_syntax_error(tmp_path: Path) -> None:
    """Files that fail to parse return False, leaving them untouched."""
    py = tmp_path / "test_a.py"
    py.write_text("from old.mod import (\n")
    assert _rewrite_file_imports(py, "old.mod", ["new.mod"]) is False
