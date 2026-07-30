"""Split from ``test_layout_and_move__stages_execute.py``."""

from axm_audit.core.fix.layout_and_move import relocate_non_canonical_tiers


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
