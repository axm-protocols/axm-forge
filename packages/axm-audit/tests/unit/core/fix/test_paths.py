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


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        pytest.param(
            "/p/tests/integration/test_X.py",
            "/p/tests/unit/test_X.py",
            id="substitution-branch",
        ),
        pytest.param(
            "/p/tests/test_X.py",
            "/p/tests/unit/test_X.py",
            id="inject-missing-tier",
        ),
        pytest.param(
            "/p/src/foo/bar.py",
            "/p/src/foo/bar.py",
            id="non-tests-unchanged",
        ),
    ],
)
def test_retier_resolves_tier_component(src: str, expected: str) -> None:
    """AC2: retier substitutes/injects the tier for tests/ paths, no-ops otherwise."""
    assert retier(Path(src), Path("/p"), "unit") == Path(expected)


def test_abspath_normalises_relative_and_absolute() -> None:
    """AC2: abspath joins relative paths to project, keeps absolute paths."""
    project = Path("/p")
    assert abspath("tests/test_x.py", project) == project / "tests" / "test_x.py"
    assert abspath("/abs/test_y.py", project) == Path("/abs/test_y.py")
