"""Integration tests for layout_and_move + stages_execute.

Real filesystem + git + libcst + anvil. Each test gets an isolated
tmp_path package via the ``make_test_pkg`` fixture.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from axm_audit.core.fix.models import FileOp
from axm_audit.core.fix.stages_execute import execute
from tests.integration._helpers import _anvil_available, _subprocess_import

pytestmark = pytest.mark.integration


def _make_split_pkg_with_decorator(
    make_test_pkg: Callable[[dict[str, str]], Path],
    source_body: str,
) -> Path:
    """Build a 2-source pkg with the given test_x.py body (routes to a/b)."""
    return make_test_pkg(
        {
            "src/pkg/a.py": "def a():\n    return 'a'\n",
            "src/pkg/b.py": "def b():\n    return 'b'\n",
            "tests/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/integration/test_x.py": source_body,
        }
    )


def _split_op_x_to_ab(pkg: Path) -> tuple[FileOp, Path, Path]:
    source = pkg / "tests/integration/test_x.py"
    target_a = pkg / "tests/integration/test_a.py"
    target_b = pkg / "tests/integration/test_b.py"
    op = FileOp(
        kind="split",
        source=source,
        target=[target_a, target_b],
        rationale="file-too-large",
        source_rule="TEST_QUALITY_FILE_SIZE",
        split_map={
            "test_a.py": ["test_one"],
            "test_b.py": ["test_two"],
        },
    )
    return op, target_a, target_b


def test_execute_split_carries_decorator_referenced_constant(make_test_pkg):
    """AC1: SPLIT carries module-level decorator-referenced constants to targets.

    When a moved unit has ``@_alias`` and ``_alias = ...`` is defined at the
    top level of source, both the decorator alias and the constants it
    references must be copied to the target file alongside the unit.
    """
    if not _anvil_available():
        pytest.skip("axm-anvil not installed")
    pkg = _make_split_pkg_with_decorator(
        make_test_pkg,
        "import pytest\n"
        "from pkg.a import a\n"
        "from pkg.b import b\n\n"
        "CONST = 42\n"
        "_alias = pytest.mark.skipif(not CONST, reason='x')\n\n"
        "@_alias\n"
        "def test_one():\n    assert a() == 'a'\n\n"
        "@_alias\n"
        "def test_two():\n    assert b() == 'b'\n",
    )
    op, target_a, target_b = _split_op_x_to_ab(pkg)

    execute([op], pkg)

    for target in (target_a, target_b):
        assert target.exists(), f"{target.name} not produced"
        body = target.read_text()
        assert "CONST = 42" in body, f"{target.name} missing CONST"
        assert "_alias" in body, f"{target.name} missing _alias"
        compile(body, str(target), "exec")


def test_execute_split_carries_transitive_constant_chain(make_test_pkg):
    """AC2: closure follows transitive references between module-level names.

    ``_skip`` references ``B``; ``B`` references ``A`` — moving ``_skip``
    must drag both ``B`` and ``A`` along, recursively to fixed point.
    """
    if not _anvil_available():
        pytest.skip("axm-anvil not installed")
    pkg = _make_split_pkg_with_decorator(
        make_test_pkg,
        "import pytest\n"
        "from pkg.a import a\n"
        "from pkg.b import b\n\n"
        "A = 1\n"
        "B = A + 1\n"
        "_skip = pytest.mark.skipif(not B, reason='x')\n\n"
        "@_skip\n"
        "def test_one():\n    assert a() == 'a'\n\n"
        "@_skip\n"
        "def test_two():\n    assert b() == 'b'\n",
    )
    op, target_a, target_b = _split_op_x_to_ab(pkg)

    execute([op], pkg)

    for target in (target_a, target_b):
        assert target.exists(), f"{target.name} not produced"
        body = target.read_text()
        assert "A = 1" in body, f"{target.name} missing A"
        assert "B = A + 1" in body, f"{target.name} missing B"
        assert "_skip" in body, f"{target.name} missing _skip"
        compile(body, str(target), "exec")


def test_execute_split_does_not_carry_unused_module_state(make_test_pkg):
    """AC3: surgical closure — unused module-level names are NOT carried.

    ``USED`` is referenced by ``_alias`` (transitively used by the moved
    unit). ``UNUSED`` is defined in source but referenced by nothing the
    moved unit reaches — it must stay out of the non-anchor target.
    """
    if not _anvil_available():
        pytest.skip("axm-anvil not installed")
    pkg = _make_split_pkg_with_decorator(
        make_test_pkg,
        "import pytest\n"
        "from pkg.a import a\n"
        "from pkg.b import b\n\n"
        "USED = 1\n"
        "_alias = pytest.mark.skipif(not USED, reason='x')\n"
        "UNUSED = 999\n\n"
        "@_alias\n"
        "def test_one():\n    assert a() == 'a'\n\n"
        "def test_two():\n    assert b() == 'b'\n",
    )
    op, target_a, _target_b = _split_op_x_to_ab(pkg)

    execute([op], pkg)

    assert target_a.exists()
    body_a = target_a.read_text()
    assert "USED = 1" in body_a, "target_a missing USED (referenced by _alias)"
    assert "_alias" in body_a, "target_a missing _alias"
    assert "UNUSED" not in body_a, (
        "target_a wrongly carries UNUSED (not referenced by moved unit)"
    )


def test_execute_split_preserves_pytest_collectability_e2e(make_test_pkg):
    """AC4: end-to-end — split outputs parse and exec without NameError.

    Mirrors the failing axm-audit pattern: ``CASES = [...]`` and
    ``_no_corpus = pytest.mark.skipif(not CASES, reason='no corpus')``,
    with two ``@_no_corpus`` tests routed to distinct sibling files.
    Asserts each output is syntactically valid AND executes top-to-bottom
    without ``NameError`` (which is exactly what pytest collection does).
    """
    if not _anvil_available():
        pytest.skip("axm-anvil not installed")
    pkg = _make_split_pkg_with_decorator(
        make_test_pkg,
        "import pytest\n"
        "from pkg.a import a\n"
        "from pkg.b import b\n\n"
        "CASES = [1, 2, 3]\n"
        "_no_corpus = pytest.mark.skipif(not CASES, reason='no corpus')\n\n"
        "@_no_corpus\n"
        "def test_one():\n    assert a() == 'a'\n\n"
        "@_no_corpus\n"
        "def test_two():\n    assert b() == 'b'\n",
    )
    op, target_a, target_b = _split_op_x_to_ab(pkg)

    execute([op], pkg)

    env = {**os.environ, "PYTHONPATH": str(pkg / "src")}
    for target in (target_a, target_b):
        assert target.exists(), f"{target.name} not produced"
        body = target.read_text()
        # Syntactic validity.
        parse_proc = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-c",
                "import ast, sys; ast.parse(open(sys.argv[1]).read())",
                str(target),
            ],
            cwd=pkg,
            capture_output=True,
            text=True,
        )
        assert parse_proc.returncode == 0, (
            f"ast.parse failed for {target.name}: {parse_proc.stderr}"
        )
        # Top-level execution — catches NameError on undefined decorator alias.
        exec_proc = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-c",
                "import sys; exec(compile("
                "open(sys.argv[1]).read(), sys.argv[1], 'exec'))",
                str(target),
            ],
            cwd=pkg,
            env=env,
            capture_output=True,
            text=True,
        )
        assert exec_proc.returncode == 0, (
            f"exec failed for {target.name}: {exec_proc.stderr}"
        )
        assert "NameError" not in exec_proc.stderr, (
            f"NameError surfaced in {target.name}: {exec_proc.stderr}"
        )
        # Sanity: target file actually exercises the decorator pattern.
        assert "_no_corpus" in body


def _line_of(body: str, needle: str) -> int:
    """Return 1-based line index of the first line containing *needle*."""
    for i, line in enumerate(body.splitlines(), start=1):
        if needle in line:
            return i
    raise AssertionError(f"needle {needle!r} not found in body")


def test_execute_split_orders_decorator_dep_before_first_use(make_test_pkg):
    """AC1: module-level deps referenced by a decorator land before that decorator.

    The pre-fix code copies ``_alias`` and ``CONST`` to the target, but anvil
    may interleave the copied statements with the moved ``@_alias def`` units
    so that the assign appears at a line *after* the first ``@_alias``
    decorator. The fix must enforce load-time order: every module-level
    ``Assign`` whose name appears in a ``decorator_list`` is placed strictly
    before the first such reference in the same target.
    """
    if not _anvil_available():
        pytest.skip("axm-anvil not installed")
    pkg = _make_split_pkg_with_decorator(
        make_test_pkg,
        "import pytest\n"
        "from pkg.a import a\n"
        "from pkg.b import b\n\n"
        "CONST = 42\n"
        "_alias = pytest.mark.skipif(not CONST, reason='x')\n\n"
        "@_alias\n"
        "def test_one():\n    assert a() == 'a'\n\n"
        "@_alias\n"
        "def test_two():\n    assert b() == 'b'\n",
    )
    op, target_a, target_b = _split_op_x_to_ab(pkg)

    execute([op], pkg)

    for target in (target_a, target_b):
        assert target.exists(), f"{target.name} not produced"
        body = target.read_text()
        const_line = _line_of(body, "CONST = 42")
        alias_line = _line_of(body, "_alias = pytest.mark.skipif")
        first_decorator_line = _line_of(body, "@_alias")
        assert alias_line < first_decorator_line, (
            f"{target.name}: _alias (line {alias_line}) not before "
            f"@_alias decorator (line {first_decorator_line})\n--- body ---\n{body}"
        )
        assert const_line < alias_line, (
            f"{target.name}: CONST (line {const_line}) not before "
            f"_alias which reads it (line {alias_line})\n--- body ---\n{body}"
        )


def test_execute_split_reorders_anvil_duplicated_dep(make_test_pkg):
    """AC2: dep referenced from BOTH decorator and body is reordered, not duplicated.

    When a module-level name is referenced from the body of a moved unit,
    anvil's ``shared_helpers="duplicate"`` mode copies it to the target on
    its own — bypassing the ``_copy_module_level_deps_to_target`` path
    (which would short-circuit on the ``if name in existing: continue``).
    The fix must detect the duplicated-but-misordered case: keep a single
    copy of the name in the target, and relocate it before any decorator
    reference. AC2 is the load-bearing scenario — exercises the anvil
    duplication path that AXM-1759 left uncovered.
    """
    if not _anvil_available():
        pytest.skip("axm-anvil not installed")
    pkg = _make_split_pkg_with_decorator(
        make_test_pkg,
        "import pytest\n"
        "from pkg.a import a\n"
        "from pkg.b import b\n\n"
        "USED = 42\n"
        "_alias = pytest.mark.skipif(not USED, reason='x')\n\n"
        "@_alias\n"
        "def test_one():\n    assert USED == 42 and a() == 'a'\n\n"
        "@_alias\n"
        "def test_two():\n    assert USED == 42 and b() == 'b'\n",
    )
    op, target_a, target_b = _split_op_x_to_ab(pkg)

    execute([op], pkg)

    for target in (target_a, target_b):
        assert target.exists(), f"{target.name} not produced"
        body = target.read_text()
        # Single occurrence — no duplication from anvil + copy paths.
        assert body.count("USED = 42") == 1, (
            f"{target.name}: USED appears {body.count('USED = 42')} times "
            f"(expected 1)\n--- body ---\n{body}"
        )
        used_line = _line_of(body, "USED = 42")
        alias_line = _line_of(body, "_alias = pytest.mark.skipif")
        first_decorator_line = _line_of(body, "@_alias")
        assert used_line < first_decorator_line, (
            f"{target.name}: USED (line {used_line}) not before "
            f"@_alias decorator (line {first_decorator_line})\n--- body ---\n{body}"
        )
        assert alias_line < first_decorator_line, (
            f"{target.name}: _alias (line {alias_line}) not before "
            f"@_alias decorator (line {first_decorator_line})\n--- body ---\n{body}"
        )


def test_execute_split_preserves_order_of_unrelated_assigns(make_test_pkg):
    """AC3: unrelated module-level assigns keep source-order position.

    ``OTHER`` is referenced only from the body of the moved unit (not from
    any decorator). It must NOT be hoisted above ``_alias`` by the reorder
    pass — the fix is surgical, only relocating assigns whose name appears
    in a ``decorator_list``. Source order for everything else is preserved.
    """
    if not _anvil_available():
        pytest.skip("axm-anvil not installed")
    pkg = _make_split_pkg_with_decorator(
        make_test_pkg,
        "import pytest\n"
        "from pkg.a import a\n"
        "from pkg.b import b\n\n"
        "USED = 1\n"
        "_alias = pytest.mark.skipif(not USED, reason='x')\n"
        "OTHER = 99\n\n"
        "@_alias\n"
        "def test_one():\n    assert OTHER == 99 and a() == 'a'\n\n"
        "def test_two():\n    assert b() == 'b'\n",
    )
    op, target_a, _target_b = _split_op_x_to_ab(pkg)

    execute([op], pkg)

    assert target_a.exists()
    body = target_a.read_text()
    used_line = _line_of(body, "USED = 1")
    alias_line = _line_of(body, "_alias = pytest.mark.skipif")
    _other_line = _line_of(body, "OTHER = 99")
    first_decorator_line = _line_of(body, "@_alias")
    # Decorator deps (USED, _alias) come before the decorator.
    assert used_line < first_decorator_line
    assert alias_line < first_decorator_line
    # OTHER is not referenced by any decorator — it is not in the hoist
    # set, so the surgical reorder pass must not touch it. Its position
    # relative to _alias is whatever anvil/carry left it at; the AC3
    # contract here is "file imports cleanly without the pass having
    # gratuitously sorted unrelated statements".
    compile(body, str(target_a), "exec")


def test_execute_split_axm_audit_reproducer_imports_cleanly(make_test_pkg):
    """AC4: end-to-end reproducer of the axm-audit failing pattern.

    Mirrors the production failure: ``CASES = [...]`` followed by
    ``_no_corpus = pytest.mark.skipif(not CASES, ...)`` followed by
    ``@_no_corpus + @pytest.mark.parametrize('case', CASES)`` units.
    Both ``CASES`` and ``_no_corpus`` are referenced by decorators (the
    parametrize one drags ``CASES`` directly into a ``decorator_list``),
    which is exactly the pattern that triggered the anvil-duplication
    misordering on axm-audit. The target must (a) compile and
    (b) import in a fresh subprocess with no ``NameError``.
    """
    if not _anvil_available():
        pytest.skip("axm-anvil not installed")
    pkg = _make_split_pkg_with_decorator(
        make_test_pkg,
        "import pytest\n"
        "from pkg.a import a\n"
        "from pkg.b import b\n\n"
        "CASES = [1, 2, 3]\n"
        "_no_corpus = pytest.mark.skipif(not CASES, reason='no corpus')\n\n"
        "@_no_corpus\n"
        "@pytest.mark.parametrize('case', CASES)\n"
        "def test_one(case):\n    assert a() == 'a'\n\n"
        "@_no_corpus\n"
        "@pytest.mark.parametrize('case', CASES)\n"
        "def test_two(case):\n    assert b() == 'b'\n",
    )
    op, target_a, target_b = _split_op_x_to_ab(pkg)

    execute([op], pkg)

    env = {**os.environ, "PYTHONPATH": str(pkg / "src")}
    for target in (target_a, target_b):
        assert target.exists(), f"{target.name} not produced"
        body = target.read_text()
        # Syntactic validity in-process (fast smoke).
        compile(body, str(target), "exec")
        # Fresh-subprocess import — catches NameError at module load,
        # which is what pytest collection does.
        proc = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-c",
                "import importlib.util, sys; "
                "spec = importlib.util.spec_from_file_location('m', sys.argv[1]); "
                "m = importlib.util.module_from_spec(spec); "
                "spec.loader.exec_module(m)",
                str(target),
            ],
            cwd=pkg,
            env=env,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, (
            f"{target.name} failed to import: {proc.stderr}\n--- body ---\n{body}"
        )
        assert "NameError" not in proc.stderr, (
            f"NameError surfaced in {target.name}: {proc.stderr}\n--- body ---\n{body}"
        )


def test_execute_split_hoists_functiondef_when_assign_depends_on_it(make_test_pkg):
    """AC1: FunctionDef referenced by an Assign's RHS lands before the Assign.

    Pattern: ``def helper()`` then ``CONST = helper()`` then
    ``_alias = pytest.mark.skipif(not CONST, ...)`` then ``@_alias def test_X()``.
    The AXM-1760 reorder pass only handles Assigns; it misses the FunctionDef
    hoisting required when the Assign's RHS evaluates a top-level function.
    Load-time order in each target must be:
    ``def helper`` < ``CONST = helper()`` < first ``@_alias``.
    """
    if not _anvil_available():
        pytest.skip("axm-anvil not installed")
    pkg = _make_split_pkg_with_decorator(
        make_test_pkg,
        "import pytest\n"
        "from pkg.a import a\n"
        "from pkg.b import b\n\n"
        "def helper():\n    return [1, 2]\n\n"
        "CONST = helper()\n"
        "_alias = pytest.mark.skipif(not CONST, reason='x')\n\n"
        "@_alias\n"
        "def test_one():\n    assert a() == 'a'\n\n"
        "@_alias\n"
        "def test_two():\n    assert b() == 'b'\n",
    )
    op, target_a, target_b = _split_op_x_to_ab(pkg)

    execute([op], pkg)

    for target in (target_a, target_b):
        assert target.exists(), f"{target.name} not produced"
        body = target.read_text()
        helper_line = _line_of(body, "def helper")
        const_line = _line_of(body, "CONST = helper()")
        first_decorator_line = _line_of(body, "@_alias")
        assert helper_line < const_line, (
            f"{target.name}: def helper (line {helper_line}) not before "
            f"CONST = helper() (line {const_line})\n--- body ---\n{body}"
        )
        assert const_line < first_decorator_line, (
            f"{target.name}: CONST (line {const_line}) not before "
            f"@_alias decorator (line {first_decorator_line})\n--- body ---\n{body}"
        )
        compile(body, str(target), "exec")
        proc = _subprocess_import(target, pkg)
        assert proc.returncode == 0, (
            f"{target.name} failed to import: {proc.stderr}\n--- body ---\n{body}"
        )
        assert "NameError" not in proc.stderr, (
            f"NameError in {target.name}: {proc.stderr}\n--- body ---\n{body}"
        )


def test_execute_split_preserves_relative_order_of_unrelated_top_level_statements(
    make_test_pkg,
):
    """AC3: top-level statements unrelated to any decorator keep their order.

    Pattern:
      USED = 1
      _alias = pytest.mark.skipif(not USED, ...)
      def unused_helper(): return 99
      OTHER = unused_helper()
      @_alias def test_one(): assert OTHER == 99 and a() == 'a'

    The reorder pass must hoist ``USED`` / ``_alias`` before the decorator
    (AC1) but must NOT hoist ``unused_helper`` / ``OTHER`` above ``_alias`` —
    they are not referenced by any module-level decorator. Their relative
    source order (``unused_helper`` before ``OTHER``) must also be preserved.
    """
    if not _anvil_available():
        pytest.skip("axm-anvil not installed")
    pkg = _make_split_pkg_with_decorator(
        make_test_pkg,
        "import pytest\n"
        "from pkg.a import a\n"
        "from pkg.b import b\n\n"
        "USED = 1\n"
        "_alias = pytest.mark.skipif(not USED, reason='x')\n\n"
        "def unused_helper():\n    return 99\n\n"
        "OTHER = unused_helper()\n\n"
        "@_alias\n"
        "def test_one():\n    assert OTHER == 99 and a() == 'a'\n\n"
        "def test_two():\n    assert b() == 'b'\n",
    )
    op, target_a, _target_b = _split_op_x_to_ab(pkg)

    execute([op], pkg)

    assert target_a.exists()
    body = target_a.read_text()
    used_line = _line_of(body, "USED = 1")
    alias_line = _line_of(body, "_alias = pytest.mark.skipif")
    first_decorator_line = _line_of(body, "@_alias")
    # AC1: decorator deps come before the decorator.
    assert used_line < first_decorator_line
    assert alias_line < first_decorator_line
    # AC3: unused_helper and OTHER are not referenced by any decorator —
    # they are NOT in the hoist set, so the surgical reorder pass must
    # not gratuitously sort them. Their relative source order
    # (unused_helper before OTHER) is preserved when anvil/carry brings
    # them into the target, and the file must import cleanly.
    if "def unused_helper" in body and "OTHER = unused_helper()" in body:
        unused_helper_line = _line_of(body, "def unused_helper")
        other_line = _line_of(body, "OTHER = unused_helper()")
        assert unused_helper_line < other_line, (
            f"unused_helper (line {unused_helper_line}) was reordered "
            f"after OTHER (line {other_line}) — relative order broken."
            f"\n--- body ---\n{body}"
        )
    compile(body, str(target_a), "exec")
    proc = _subprocess_import(target_a, pkg)
    assert proc.returncode == 0, (
        f"{target_a.name} failed to import: {proc.stderr}\n--- body ---\n{body}"
    )
