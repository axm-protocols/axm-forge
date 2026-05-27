"""Unit tests for axm_audit.core.fix.tests_ast read-only AST helpers.

Covers the internal-public helpers exposed by ``tests_ast``.
"""

from __future__ import annotations

import ast
from pathlib import Path

from axm_audit.core.fix.findings import class_needs_flatten
from axm_audit.core.fix.tests_ast import (
    class_is_pathological,
    collect_imported_names,
    file_has_pathological_class,
    func_body_hash,
    marker_fixtures_in_unit,
    top_level_helpers,
    top_level_test_classes,
)


def _parse_source(src: str) -> ast.Module:
    """Parse a string into an in-memory ast.Module (Task 1 fixture)."""
    return ast.parse(src)


def test_top_level_test_classes_filters_underscored_and_nested() -> None:
    """AC1: only Test* classes at module level with test_* methods."""
    src = (
        "class TestA:\n"
        "    def test_a(self): pass\n"
        "class _TestB:\n"
        "    def test_b(self): pass\n"
        "class TestC:\n"
        "    def test_c(self): pass\n"
        "    class TestInner:\n"
        "        def test_inner(self): pass\n"
    )
    tree = _parse_source(src)
    names = {c.name for c in top_level_test_classes(tree)}
    assert names == {"TestA", "TestC"}


def test_class_is_pathological_uses_self_x() -> None:
    """AC2: detects ``self.<attr>`` access in test method."""
    src = "class TestF:\n    def test_x(self):\n        self.foo = 1\n"
    cls = _parse_source(src).body[0]
    assert isinstance(cls, ast.ClassDef)
    reason = class_is_pathological(cls)
    assert reason is not None
    assert "self" in reason


def test_class_is_pathological_non_object_inheritance() -> None:
    """AC2: detects inheritance from a non-object base."""
    src = "class TestF(SomeBase):\n    def test_x(self): pass\n"
    cls = _parse_source(src).body[0]
    assert isinstance(cls, ast.ClassDef)
    reason = class_is_pathological(cls)
    assert reason is not None
    assert "inherits" in reason


def test_class_is_pathological_has_init() -> None:
    """AC2: detects presence of __init__."""
    src = "class TestF:\n    def __init__(self): pass\n"
    cls = _parse_source(src).body[0]
    assert isinstance(cls, ast.ClassDef)
    reason = class_is_pathological(cls)
    assert reason is not None
    assert "__init__" in reason


def test_class_is_pathological_benign_returns_none() -> None:
    """AC2: benign class returns None."""
    src = "class TestF:\n    def test_x(self):\n        assert True\n"
    cls = _parse_source(src).body[0]
    assert isinstance(cls, ast.ClassDef)
    assert class_is_pathological(cls) is None


def test_class_needs_flatten_divergent_tuples() -> None:
    """AC3: methods with divergent first-party symbol calls -> True."""
    src = (
        "from pkg import symA, symB\n"
        "class TestC:\n"
        "    def test_a(self):\n"
        "        symA()\n"
        "    def test_b(self):\n"
        "        symB()\n"
    )
    tree = _parse_source(src)
    cls = tree.body[1]
    assert isinstance(cls, ast.ClassDef)
    assert (
        class_needs_flatten(
            cls,
            tree,
            tier="integration",
            pkg_prefixes={"pkg"},
            scripts=set(),
            single_binary=None,
        )
        is True
    )


def test_class_needs_flatten_homogeneous_tuples_false() -> None:
    """AC3: methods calling identical first-party symbols -> False."""
    src = (
        "import pkg\n"
        "class TestC:\n"
        "    def test_a(self):\n"
        "        pkg.symA()\n"
        "        pkg.symB()\n"
        "    def test_b(self):\n"
        "        pkg.symA()\n"
        "        pkg.symB()\n"
    )
    tree = _parse_source(src)
    cls = tree.body[1]
    assert isinstance(cls, ast.ClassDef)
    assert (
        class_needs_flatten(
            cls,
            tree,
            tier="integration",
            pkg_prefixes={"pkg"},
            scripts=set(),
            single_binary=None,
        )
        is False
    )


def test_file_has_pathological_class_true_false(tmp_path: Path) -> None:
    """AC4: True iff file contains pathological class with divergent canonical."""
    benign = tmp_path / "test_benign.py"
    benign.write_text("class TestB:\n    def test_a(self): pass\n")
    assert file_has_pathological_class(benign) is False

    bad = tmp_path / "test_bad.py"
    bad.write_text(
        "class TestX:\n"
        "    def __init__(self): pass\n"
        "    def test_alpha_one(self): pass\n"
        "    def test_beta_two(self): pass\n"
    )
    assert file_has_pathological_class(bad) is True


def test_top_level_helpers_filters_test_prefix() -> None:
    """AC5: top-level non-test FunctionDef only (no test_*, no Test* class)."""
    src = (
        "def helper():\n    return 1\n"
        "def test_x(): pass\n"
        "class TestC:\n"
        "    def helper(self): pass\n"
    )
    tree = _parse_source(src)
    helpers = top_level_helpers(tree)
    assert set(helpers.keys()) == {"helper"}


def test_collect_imported_names_aliased_and_future_ignored() -> None:
    """AC6: aliased imports yield local name; basic imports yield module name."""
    src = "from __future__ import annotations\nimport os\nfrom typing import Any as A\n"
    tree = _parse_source(src)
    result = collect_imported_names(tree)
    assert "os" in result
    assert "A" in result


def test_marker_fixtures_in_unit_usefixtures_marker() -> None:
    """AC7: extracts string args from @pytest.mark.usefixtures(...)."""
    src = "import pytest\n@pytest.mark.usefixtures('a', 'b')\ndef test_x(): pass\n"
    tree = _parse_source(src)
    func = tree.body[1]
    assert isinstance(func, ast.FunctionDef)
    assert marker_fixtures_in_unit(func) == {"a", "b"}


def test_func_body_hash_ignores_docstring() -> None:
    """AC8: identical bodies modulo docstring -> same hash."""
    src1 = 'def f():\n    """doc"""\n    x = 1\n    return x\n'
    src2 = "def f():\n    x = 1\n    return x\n"
    f1 = _parse_source(src1).body[0]
    f2 = _parse_source(src2).body[0]
    assert isinstance(f1, ast.FunctionDef)
    assert isinstance(f2, ast.FunctionDef)
    assert func_body_hash(f1) == func_body_hash(f2)


def test_func_body_hash_diverges_on_assert_change() -> None:
    """AC8: differing assert literal -> different hash."""
    src1 = "def f(x):\n    assert x == 1\n"
    src2 = "def f(x):\n    assert x == 2\n"
    f1 = _parse_source(src1).body[0]
    f2 = _parse_source(src2).body[0]
    assert isinstance(f1, ast.FunctionDef)
    assert isinstance(f2, ast.FunctionDef)
    assert func_body_hash(f1) != func_body_hash(f2)
