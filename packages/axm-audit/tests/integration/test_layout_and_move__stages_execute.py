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

from axm_audit.core.fix.layout_and_move import (
    flatten_tier_layout,
    relocate_non_canonical_tiers,
)
from axm_audit.core.fix.models import FileOp
from axm_audit.core.fix.stages_execute import execute

pytestmark = pytest.mark.integration


def _anvil_available() -> bool:
    try:
        from axm_audit.core.fix.layout_and_move import move_symbols
    except ImportError:
        return False
    return move_symbols is not None


@pytest.fixture
def make_test_pkg(tmp_path: Path) -> Callable[[dict[str, str]], Path]:
    """Build a minimal git-initialised package with the given source files."""

    def _make(sources: dict[str, str]) -> Path:
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "pyproject.toml").write_text(
            '[project]\nname = "pkg"\nversion = "0.0.0"\nrequires-python = ">=3.12"\n'
        )
        (pkg / "src").mkdir()
        (pkg / "src" / "pkg").mkdir()
        (pkg / "src" / "pkg" / "__init__.py").write_text("")
        (pkg / "tests").mkdir()
        for rel, content in sources.items():
            f = pkg / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content)
        subprocess.run(["git", "init", "-q"], cwd=pkg, check=True, capture_output=True)  # noqa: S607
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=pkg, check=True)  # noqa: S607
        subprocess.run(["git", "config", "user.name", "t"], cwd=pkg, check=True)  # noqa: S607
        subprocess.run(["git", "add", "-A"], cwd=pkg, check=True, capture_output=True)  # noqa: S607
        subprocess.run(
            ["git", "commit", "-q", "-m", "init"],  # noqa: S607
            cwd=pkg,
            check=True,
            capture_output=True,
        )
        return pkg

    return _make


def test_relocate_non_canonical_tiers_moves_functional_to_integration(
    make_test_pkg,
):
    """AC1: tests/functional/test_x.py -> tests/integration/test_x.py."""
    pkg = make_test_pkg(
        {
            "tests/functional/test_x.py": "def test_one():\n    assert True\n",
        }
    )

    relocate_non_canonical_tiers(pkg)

    assert (pkg / "tests" / "integration" / "test_x.py").exists()
    assert not (pkg / "tests" / "functional").exists()


def test_flatten_tier_layout_collapses_subdirectory(make_test_pkg):
    """AC2: tests/integration/foo/test_x.py -> tests/integration/test_x.py."""
    pkg = make_test_pkg(
        {
            "tests/integration/foo/test_x.py": ("def test_one():\n    assert True\n"),
        }
    )

    flatten_tier_layout(pkg)

    assert (pkg / "tests" / "integration" / "test_x.py").exists()


def test_flatten_tier_layout_refuses_on_collision(make_test_pkg):
    """AC2: flatten preserves both files on tier-root name collision."""
    pkg = make_test_pkg(
        {
            "tests/integration/test_x.py": ("def test_one():\n    assert True\n"),
            "tests/integration/foo/test_x.py": ("def test_two():\n    assert True\n"),
        }
    )

    msgs = flatten_tier_layout(pkg)

    # Original at tier root is preserved as-is.
    original = (pkg / "tests" / "integration" / "test_x.py").read_text()
    assert "test_one" in original
    # The nested file's contents survive — either renamed at tier root
    # (e.g. test_foo_x.py) or left in place when flatten refuses.
    renamed_candidates = list((pkg / "tests" / "integration").glob("test_*.py"))
    nested_kept = (pkg / "tests" / "integration" / "foo" / "test_x.py").exists()
    survived = nested_kept or any(
        "test_two" in p.read_text() for p in renamed_candidates
    )
    assert survived
    # Some signal — either a rename msg or a warning — must be surfaced.
    assert msgs


def test_execute_merge_renames_helpers_with_divergent_bodies(make_test_pkg):
    """AC4: merging into target with a same-name but divergent helper renames
    source's helper with the ``__from_<source_stem>`` suffix so anvil can
    duplicate it into target without colliding with target's own body.

    Exercised through the public ``execute(merge)`` seam — the rename is
    a transparent step of ``_safe_move_units``, and the observable
    outcome is the suffixed name landing in the merged target file.
    """
    if not _anvil_available():
        pytest.skip("axm-anvil not installed")
    source_code = (
        "def _helper(x):\n"
        "    return x + 1\n\n"
        "def test_one():\n"
        "    assert _helper(1) == 2\n"
    )
    target_code = (
        "def _helper(x):\n"
        "    return x + 2\n\n"
        "def test_two():\n"
        "    assert _helper(1) == 3\n"
    )
    pkg = make_test_pkg(
        {
            "tests/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/integration/test_a.py": source_code,
            "tests/integration/test_b.py": target_code,
        }
    )
    source = pkg / "tests/integration/test_a.py"
    target = pkg / "tests/integration/test_b.py"
    op = FileOp(
        kind="merge",
        source=source,
        target=target,
        rationale="too-small",
        source_rule="TEST_QUALITY_FILE_SIZE",
    )

    execute([op], pkg)

    body = target.read_text()
    # Source's _helper was renamed with the __from_<source_stem> suffix
    # so both helper bodies can co-exist in the merged target.
    assert "_helper__from_a" in body
    # Target's original helper body is preserved.
    assert "return x + 2" in body
    # The moved test now references the renamed helper.
    assert "_helper__from_a(1) == 2" in body


def test_execute_merge_renames_target_local_fixture_shadowing_conftest(
    make_test_pkg,
):
    """AC5: merging tests that rely on a conftest fixture into a target
    that defines a same-named local fixture renames the target's local
    with the ``__local_<target_stem>`` suffix, so moved tests bind to
    the conftest fixture while target's existing tests keep their
    original (renamed) local body.

    Exercised through the public ``execute(merge)`` seam — the rename
    is a transparent step of ``_safe_move_units``, and the observable
    outcome is the suffixed name landing in the merged target file.
    """
    if not _anvil_available():
        pytest.skip("axm-anvil not installed")
    conftest = "import pytest\n\n@pytest.fixture\ndef shared_fix():\n    return 1\n"
    source_code = "def test_one(shared_fix):\n    assert shared_fix == 1\n"
    target_code = (
        "import pytest\n\n"
        "@pytest.fixture\n"
        "def shared_fix():\n"
        "    return 99\n\n"
        "def test_two(shared_fix):\n"
        "    assert shared_fix == 99\n"
    )
    pkg = make_test_pkg(
        {
            "tests/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/conftest.py": conftest,
            "tests/integration/test_a.py": source_code,
            "tests/integration/test_b.py": target_code,
        }
    )
    source = pkg / "tests/integration/test_a.py"
    target = pkg / "tests/integration/test_b.py"
    op = FileOp(
        kind="merge",
        source=source,
        target=target,
        rationale="too-small",
        source_rule="TEST_QUALITY_FILE_SIZE",
    )

    execute([op], pkg)

    body = target.read_text()
    # Target's local shared_fix was renamed to avoid shadowing conftest
    # for the moved test.
    assert "shared_fix__local_b" in body
    # Target's own test now references the renamed local fixture.
    assert "shared_fix__local_b" in body.split("def test_two")[1]


def test_execute_relocate_cross_tier_with_depth_patch(make_test_pkg):
    """AC6: relocate across tiers patches Path(__file__).parents[N] depth."""
    body = (
        "from pathlib import Path\n\n"
        "def test_one():\n"
        "    root = Path(__file__).parents[2]\n"
        "    assert root.exists()\n"
    )
    pkg = make_test_pkg(
        {
            "tests/integration/foo/test_x.py": body,
        }
    )
    source = pkg / "tests/integration/foo/test_x.py"
    target = pkg / "tests/unit/test_x.py"
    op = FileOp(
        kind="relocate",
        source=source,
        target=target,
        rationale="re-tier",
        source_rule="PYRAMID_LEVEL",
    )

    execute([op], pkg)

    assert target.exists()
    assert "parents[1]" in target.read_text()


def test_execute_rename_updates_cross_imports(make_test_pkg):
    """AC7: rename git-mvs the file and rewrites cross-test imports."""
    pkg = make_test_pkg(
        {
            "tests/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/integration/test_old.py": ("def helper():\n    return 1\n"),
            "tests/integration/test_other.py": (
                "from tests.integration.test_old import helper\n\n"
                "def test_one():\n"
                "    assert helper() == 1\n"
            ),
        }
    )
    source = pkg / "tests/integration/test_old.py"
    target = pkg / "tests/integration/test_new.py"
    op = FileOp(
        kind="rename",
        source=source,
        target=target,
        rationale="canonical-name",
        source_rule="TEST_QUALITY_FILE_NAMING",
    )

    execute([op], pkg)

    assert target.exists()
    other = (pkg / "tests/integration/test_other.py").read_text()
    assert "test_new" in other


def test_execute_split_produces_target_files(make_test_pkg):
    """AC8: split produces N target files from one source.

    Routing is derived from each unit's first-party symbol usage via
    ``_per_unit_canonical`` — not from ``split_map`` alone. The two
    units must therefore exercise distinct first-party symbols so the
    executor canonicalises them to sibling files.
    """
    if not _anvil_available():
        pytest.skip("axm-anvil not installed")
    pkg = make_test_pkg(
        {
            "src/pkg/a.py": "def a():\n    return 'a'\n",
            "src/pkg/b.py": "def b():\n    return 'b'\n",
            "tests/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/integration/test_x.py": (
                "from pkg.a import a\n"
                "from pkg.b import b\n\n"
                "def test_one():\n    assert a() == 'a'\n\n"
                "def test_two():\n    assert b() == 'b'\n"
            ),
        }
    )
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

    execute([op], pkg)

    assert target_a.exists()
    assert target_b.exists()


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


def test_execute_merge_concatenates_units_into_anchor(make_test_pkg):
    """AC9: merge moves all units into target and removes source."""
    if not _anvil_available():
        pytest.skip("axm-anvil not installed")
    pkg = make_test_pkg(
        {
            "tests/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/integration/test_a.py": ("def test_alpha():\n    assert True\n"),
            "tests/integration/test_b.py": ("def test_beta():\n    assert True\n"),
        }
    )
    source = pkg / "tests/integration/test_b.py"
    target = pkg / "tests/integration/test_a.py"
    op = FileOp(
        kind="merge",
        source=source,
        target=target,
        rationale="too-small",
        source_rule="TEST_QUALITY_FILE_SIZE",
    )

    execute([op], pkg)

    assert not source.exists()
    body = target.read_text()
    assert "test_beta" in body
    assert "test_alpha" in body


def test_execute_flatten_converts_class_to_top_level(make_test_pkg):
    """AC10: flatten converts a Test* class to top-level functions in place."""
    pkg = make_test_pkg(
        {
            "tests/integration/test_x.py": (
                "class TestX:\n    def test_one(self):\n        assert True\n"
            ),
        }
    )
    source = pkg / "tests/integration/test_x.py"
    op = FileOp(
        kind="flatten",
        source=source,
        target=source,
        rationale="heterogeneous-class",
        source_rule="TEST_QUALITY_CLASS_FLAT",
        split_map={"TestX": []},
    )

    execute([op], pkg)

    text = source.read_text()
    assert "class TestX" not in text


def test_relocate_non_canonical_tiers_skips_fixtures_dir(make_test_pkg):
    """AC1, AC2: tests/fixtures/ with nested test_*.py is a no-op."""
    pkg = make_test_pkg(
        {
            "tests/fixtures/fix_corpus/case_x/input/tests/integration/test_alpha.py": (
                "def test_one():\n    assert True\n"
            ),
        }
    )

    msgs = relocate_non_canonical_tiers(pkg)

    assert msgs == []
    assert (
        pkg
        / "tests"
        / "fixtures"
        / "fix_corpus"
        / "case_x"
        / "input"
        / "tests"
        / "integration"
        / "test_alpha.py"
    ).exists()
    assert not (pkg / "tests" / "integration").exists()


def test_relocate_non_canonical_tiers_skips_nested_fixtures_test_files(
    make_test_pkg,
):
    """AC2: deep fixture trees with test_*.py files are untouched."""
    pkg = make_test_pkg(
        {
            "tests/fixtures/fix_corpus/case_a/input/tests/unit/test_x.py": (
                "def test_one():\n    assert True\n"
            ),
            "tests/fixtures/fix_corpus/case_a/expected/tests/integration/test_y.py": (
                "def test_one():\n    assert True\n"
            ),
            "tests/fixtures/snapshots/test_z.py": (
                "def test_one():\n    assert True\n"
            ),
        }
    )

    relocate_non_canonical_tiers(pkg)

    assert (
        pkg / "tests/fixtures/fix_corpus/case_a/input/tests/unit/test_x.py"
    ).exists()
    assert (
        pkg / "tests/fixtures/fix_corpus/case_a/expected/tests/integration/test_y.py"
    ).exists()
    assert (pkg / "tests/fixtures/snapshots/test_z.py").exists()
    assert not (pkg / "tests" / "integration").exists()


def test_relocate_non_canonical_tiers_fixtures_alongside_functional(make_test_pkg):
    """AC3: fixtures preserved while sibling functional/ is still relocated."""
    pkg = make_test_pkg(
        {
            "tests/functional/test_a.py": "def test_one():\n    assert True\n",
            "tests/fixtures/case_x/input/tests/integration/test_b.py": (
                "def test_one():\n    assert True\n"
            ),
        }
    )

    relocate_non_canonical_tiers(pkg)

    assert (pkg / "tests" / "integration" / "test_a.py").exists()
    assert not (pkg / "tests" / "functional").exists()
    assert (pkg / "tests/fixtures/case_x/input/tests/integration/test_b.py").exists()
    assert not (pkg / "tests" / "integration" / "test_b.py").exists()
