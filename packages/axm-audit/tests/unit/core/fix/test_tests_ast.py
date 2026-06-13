"""Unit tests for axm_audit.core.fix.tests_ast read-only AST helpers.

Covers the internal-public helpers exposed by ``tests_ast``.
"""

from __future__ import annotations

import ast

import pytest

from axm_audit.core.fix.findings import class_needs_flatten
from axm_audit.core.fix.tests_ast import (
    class_is_pathological,
    collect_imported_names,
    collect_referenced_names,
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


@pytest.mark.parametrize(
    ("src", "marker"),
    [
        pytest.param(
            "class TestF:\n    def test_x(self):\n        self.foo = 1\n",
            "self",
            id="uses-self-attr",
        ),
        pytest.param(
            "class TestF(SomeBase):\n    def test_x(self): pass\n",
            "inherits",
            id="non-object-inheritance",
        ),
        pytest.param(
            "class TestF:\n    def __init__(self): pass\n",
            "__init__",
            id="has-init",
        ),
    ],
)
def test_class_is_pathological_detects(src: str, marker: str) -> None:
    """AC2: pathological classes return a reason naming the offending trait."""
    cls = _parse_source(src).body[0]
    assert isinstance(cls, ast.ClassDef)
    reason = class_is_pathological(cls)
    assert reason is not None
    assert marker in reason


def test_class_is_pathological_benign_returns_none() -> None:
    """AC2: benign class returns None."""
    src = "class TestF:\n    def test_x(self):\n        assert True\n"
    cls = _parse_source(src).body[0]
    assert isinstance(cls, ast.ClassDef)
    assert class_is_pathological(cls) is None


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        pytest.param(
            "from pkg import symA, symB\n"
            "class TestC:\n"
            "    def test_a(self):\n"
            "        symA()\n"
            "    def test_b(self):\n"
            "        symB()\n",
            True,
            id="divergent-tuples",
        ),
        pytest.param(
            "import pkg\n"
            "class TestC:\n"
            "    def test_a(self):\n"
            "        pkg.symA()\n"
            "        pkg.symB()\n"
            "    def test_b(self):\n"
            "        pkg.symA()\n"
            "        pkg.symB()\n",
            False,
            id="homogeneous-tuples",
        ),
    ],
)
def test_class_needs_flatten_tuples(src: str, expected: bool) -> None:
    """AC3: integration flatten fires only when method symbol-tuples diverge."""
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
        is expected
    )


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


@pytest.mark.parametrize(
    ("src", "present", "absent"),
    [
        pytest.param(
            "from __future__ import annotations\n"
            "import os\nfrom typing import Any as A\n",
            ("os", "A"),
            (),
            id="aliased-and-future-ignored",
        ),
        pytest.param(
            "import os.path\nimport json\n",
            ("os", "json"),
            (),
            id="module-import",
        ),
        pytest.param(
            "from typing import Any, List as L\n",
            ("Any", "L"),
            ("List",),  # aliased — the alias replaces the original
            id="from-with-multiple-aliases",
        ),
    ],
)
def test_collect_imported_names(
    src: str, present: tuple[str, ...], absent: tuple[str, ...]
) -> None:
    """AC6: import/from/alias forms surface bound names (alias replaces origin)."""
    names = collect_imported_names(_parse_source(src))
    for name in present:
        assert name in names
    for name in absent:
        assert name not in names


@pytest.mark.parametrize(
    ("src", "func_index", "expected"),
    [
        pytest.param(
            "import pytest\n@pytest.mark.usefixtures('a', 'b')\ndef test_x(): pass\n",
            1,
            {"a", "b"},
            id="usefixtures_marker",
        ),
        pytest.param(
            "def test_x():\n    pass\n",
            0,
            set(),
            id="returns_empty_when_no_decorator",
        ),
    ],
)
def test_marker_fixtures_in_unit(src: str, func_index: int, expected: set[str]) -> None:
    """AC7: usefixtures(...) string args are extracted; bare functions yield none."""
    tree = _parse_source(src)
    func = tree.body[func_index]
    assert isinstance(func, ast.FunctionDef)
    assert marker_fixtures_in_unit(func) == expected


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


# ---------------------------------------------------------------------------
# top_level_helpers — module-level helper inventory
# ---------------------------------------------------------------------------


def test_top_level_helpers_includes_functions_and_classes() -> None:
    """top_level_helpers returns top-level FunctionDef + non-Test ClassDef."""
    src = (
        "def helper(): return 1\n"
        "class Util: pass\n"
        "class TestX:\n    def test_a(self): pass\n"
    )
    tree = _parse_source(src)
    out = top_level_helpers(tree)
    names = set(out.keys())
    assert "helper" in names
    assert "Util" in names
    assert "TestX" not in names


def test_top_level_helpers_includes_uppercase_constants() -> None:
    """Single-target UPPERCASE assignments are helpers (constants)."""
    src = "CONST = 42\nlower = 1\n"
    tree = _parse_source(src)
    out = top_level_helpers(tree)
    assert "CONST" in out
    assert "lower" not in out


def test_top_level_helpers_skips_test_functions() -> None:
    """Functions starting with ``test_`` are NOT helpers.

    They are tests in their own right and are excluded so that the
    helper inventory only contains scaffolding.
    """
    src = "def test_x(): pass\ndef helper(): pass\n"
    tree = _parse_source(src)
    out = top_level_helpers(tree)
    assert set(out.keys()) == {"helper"}


# ---------------------------------------------------------------------------
# collect_imported_names — boundary cases
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# class_needs_flatten — e2e tier
# ---------------------------------------------------------------------------


def test_class_needs_flatten_e2e_divergent_clis() -> None:
    """For e2e tier, divergent CLI invocations also force a flatten."""
    src = (
        "import subprocess\n"
        "class TestE2E:\n"
        "    def test_a(self):\n"
        "        subprocess.run(['cli_a', '--arg'])\n"
        "    def test_b(self):\n"
        "        subprocess.run(['cli_b', '--arg'])\n"
    )
    tree = _parse_source(src)
    cls = tree.body[1]
    assert isinstance(cls, ast.ClassDef)
    needs = class_needs_flatten(
        cls,
        tree,
        tier="e2e",
        pkg_prefixes=set(),
        scripts={"cli_a", "cli_b"},
        single_binary=None,
    )
    assert needs is True


def test_class_needs_flatten_single_method_returns_false() -> None:
    """A class with only one test method has a single canonical -> no flatten."""
    src = "from pkg import symA\nclass TestC:\n    def test_a(self):\n        symA()\n"
    tree = _parse_source(src)
    cls = tree.body[1]
    assert isinstance(cls, ast.ClassDef)
    needs = class_needs_flatten(
        cls,
        tree,
        tier="integration",
        pkg_prefixes={"pkg"},
        scripts=set(),
        single_binary=None,
    )
    assert needs is False


# ---------------------------------------------------------------------------
# collect_referenced_names — method-parameter annotations (AXM-1768)
# ---------------------------------------------------------------------------


def test_collects_mockerfixture_method_param_annotation() -> None:
    """AC3: a name used only in a method-parameter annotation under a ClassDef
    is reached by referenced-name collection so import backfill can carry it.
    """
    src = (
        "class TestThing:\n"
        "    def test_it(self, mocker: MockerFixture) -> None:\n"
        "        assert mocker is not None\n"
    )
    tree = _parse_source(src)
    result = collect_referenced_names(tree)
    assert "MockerFixture" in result
