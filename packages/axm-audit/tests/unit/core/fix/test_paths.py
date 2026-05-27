"""Unit tests for axm_audit.core.fix.paths — AC2."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.paths import (
    abspath,
    retier,
    safe_filename,
    tier_for_path,
)


@pytest.mark.parametrize(
    ("inp", "expected"),
    [
        ("test_a-b.py", "test_a__b.py"),
        ("test_x.py", "test_x.py"),
        ("not_a_pyfile", "not_a_pyfile"),
    ],
)
def test_safe_filename_substitutes_dash(inp: str, expected: str) -> None:
    """AC2: safe_filename replaces legacy `-` separators, no-ops otherwise."""
    assert safe_filename(inp) == expected


@pytest.mark.parametrize(
    ("path_str", "expected"),
    [
        ("tests/integration/hooks/test_x.py", "integration"),
        ("tests/e2e/test_x.py", "e2e"),
        ("src/foo/bar.py", None),
    ],
)
def test_tier_for_path_finds_nested(path_str: str, expected: str | None) -> None:
    """AC2: tier_for_path walks parts to find the tier component."""
    assert tier_for_path(Path(path_str)) == expected


def test_retier_substitution_branch() -> None:
    """AC2: retier substitutes the tier component for tests/<tier>/...rest."""
    root = Path("/p")
    src = Path("/p/tests/integration/test_X.py")
    assert retier(src, root, "unit") == Path("/p/tests/unit/test_X.py")


def test_retier_inject_missing_tier() -> None:
    """AC2: retier injects tier when path is tests/<file>.py (depth-2 corner case)."""
    root = Path("/p")
    src = Path("/p/tests/test_X.py")
    assert retier(src, root, "unit") == Path("/p/tests/unit/test_X.py")


def test_retier_non_tests_unchanged() -> None:
    """AC2: retier returns paths outside tests/ unchanged."""
    root = Path("/p")
    src = Path("/p/src/foo/bar.py")
    assert retier(src, root, "unit") == Path("/p/src/foo/bar.py")


def test_abspath_normalises_relative_and_absolute() -> None:
    """AC2: abspath joins relative paths to project, keeps absolute paths."""
    project = Path("/p")
    assert abspath("tests/test_x.py", project) == project / "tests" / "test_x.py"
    assert abspath("/abs/test_y.py", project) == Path("/abs/test_y.py")
