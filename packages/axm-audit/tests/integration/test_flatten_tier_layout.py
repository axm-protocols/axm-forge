"""Split from ``test_layout_and_move__stages_execute.py``."""

from axm_audit.core.fix.layout_and_move import flatten_tier_layout


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
