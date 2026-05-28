"""Split from ``test_layout_and_move__stages_execute.py``."""

import pytest

from axm_audit.core.fix.models import FileOp
from axm_audit.core.fix.stages_execute import execute
from tests.integration._helpers import _anvil_available, _subprocess_import


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


def test_execute_split_orders_multi_source_target_correctly(make_test_pkg):
    """AC2: target hit by multiple FileOps converges to a load-time-correct order.

    Three sources merge into the same target. Each source contributes its own
    helper + decorator alias + a moved unit. The reorder pass must respect the
    dependency graph across ALL contributing sources, not just the last one to
    land. End test: ``test_shared.py`` imports without ``NameError`` in a fresh
    subprocess.
    """
    if not _anvil_available():
        pytest.skip("axm-anvil not installed")

    def src_body(letter: str) -> str:
        upper = letter.upper()
        return (
            "import pytest\n"
            f"from pkg.{letter} import {letter}\n\n"
            f"def helper_{letter}():\n    return [{letter!r}]\n\n"
            f"CONST_{upper} = helper_{letter}()\n"
            f"_alias_{letter} = pytest.mark.skipif("
            f"not CONST_{upper}, reason='{letter}')\n\n"
            f"@_alias_{letter}\n"
            f"def test_{letter}_one():\n    assert {letter}() == {letter!r}\n"
        )

    pkg = make_test_pkg(
        {
            "src/pkg/a.py": "def a():\n    return 'a'\n",
            "src/pkg/b.py": "def b():\n    return 'b'\n",
            "src/pkg/c.py": "def c():\n    return 'c'\n",
            "tests/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/integration/test_src_a.py": src_body("a"),
            "tests/integration/test_src_b.py": src_body("b"),
            "tests/integration/test_src_c.py": src_body("c"),
            "tests/integration/test_shared.py": '"""Shared merge target."""\n',
        }
    )
    shared = pkg / "tests/integration/test_shared.py"

    def merge_op(letter: str) -> FileOp:
        return FileOp(
            kind="merge",
            source=pkg / f"tests/integration/test_src_{letter}.py",
            target=shared,
            rationale="too-small",
            source_rule="TEST_QUALITY_FILE_SIZE",
        )

    execute([merge_op("a"), merge_op("b"), merge_op("c")], pkg)

    assert shared.exists(), "test_shared.py was not produced by the merges"
    body = shared.read_text()
    compile(body, str(shared), "exec")
    proc = _subprocess_import(shared, pkg)
    assert proc.returncode == 0, (
        f"test_shared.py failed to import: {proc.stderr}\n--- body ---\n{body}"
    )
    assert "NameError" not in proc.stderr, (
        f"NameError in test_shared.py: {proc.stderr}\n--- body ---\n{body}"
    )


def test_execute_split_axm_audit_reproducer_imports_after_full_stack(
    make_test_pkg,
):
    """AC4: end-to-end reproducer of the axm-audit failing pattern.

    Two-stage pipeline:
      * SPLIT ``test_x.py`` -> ``test_a.py`` + ``test_b.py``.
      * MERGE ``test_y.py`` -> ``test_a.py`` (multi-source target case).

    Each source mirrors the production failure:
      def _corpus_cases(): return ['a', 'b']
      CASES = _corpus_cases()
      _no_corpus = pytest.mark.skipif(not CASES, ...)
      @_no_corpus @pytest.mark.parametrize('case', CASES) def test_X(case)

    Every output file must (a) compile and (b) import in a fresh subprocess
    with no ``NameError`` — covering AC1 (FunctionDef closure) + AC2
    (multi-source target order) + AC3 (surgical) end-to-end.
    """
    if not _anvil_available():
        pytest.skip("axm-anvil not installed")

    def body_with_pattern(unit_a: str, unit_b: str) -> str:
        return (
            "import pytest\n"
            "from pkg.a import a\n"
            "from pkg.b import b\n\n"
            "def _corpus_cases():\n    return ['a', 'b']\n\n"
            "CASES = _corpus_cases()\n"
            "_no_corpus = pytest.mark.skipif(not CASES, reason='no corpus')\n\n"
            "@_no_corpus\n"
            "@pytest.mark.parametrize('case', CASES)\n"
            f"def {unit_a}(case):\n    assert a() == 'a'\n\n"
            "@_no_corpus\n"
            "@pytest.mark.parametrize('case', CASES)\n"
            f"def {unit_b}(case):\n    assert b() == 'b'\n"
        )

    pkg = make_test_pkg(
        {
            "src/pkg/a.py": "def a():\n    return 'a'\n",
            "src/pkg/b.py": "def b():\n    return 'b'\n",
            "tests/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/integration/test_x.py": body_with_pattern("test_one", "test_two"),
            "tests/integration/test_y.py": body_with_pattern("test_three", "test_four"),
        }
    )
    source_x = pkg / "tests/integration/test_x.py"
    source_y = pkg / "tests/integration/test_y.py"
    target_a = pkg / "tests/integration/test_a.py"
    target_b = pkg / "tests/integration/test_b.py"
    split_op = FileOp(
        kind="split",
        source=source_x,
        target=[target_a, target_b],
        rationale="file-too-large",
        source_rule="TEST_QUALITY_FILE_SIZE",
        split_map={
            "test_a.py": ["test_one"],
            "test_b.py": ["test_two"],
        },
    )
    merge_op = FileOp(
        kind="merge",
        source=source_y,
        target=target_a,
        rationale="too-small",
        source_rule="TEST_QUALITY_FILE_SIZE",
    )

    execute([split_op, merge_op], pkg)

    output_targets = [p for p in (target_a, target_b) if p.exists()]
    assert output_targets, "No split/merge output produced"
    for target in output_targets:
        body = target.read_text()
        compile(body, str(target), "exec")
        proc = _subprocess_import(target, pkg)
        assert proc.returncode == 0, (
            f"{target.name} failed to import: {proc.stderr}\n--- body ---\n{body}"
        )
        assert "NameError" not in proc.stderr, (
            f"NameError in {target.name}: {proc.stderr}\n--- body ---\n{body}"
        )


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
