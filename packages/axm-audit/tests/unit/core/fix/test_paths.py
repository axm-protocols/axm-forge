"""Unit tests for axm_audit.core.fix.paths — AC2."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.paths import (
    abspath,
    file_depth_from_project,
    module_path_for_test_file,
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


def test_module_path_dotted_and_outside(tmp_path: Path) -> None:
    """AC2: module_path_for_test_file returns dotted path or None outside project."""
    project = tmp_path / "p"
    test_file = project / "tests" / "integration" / "test_foo.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("")
    assert module_path_for_test_file(test_file, project) == "tests.integration.test_foo"

    outside = tmp_path / "elsewhere" / "test_foo.py"
    outside.parent.mkdir(parents=True)
    outside.write_text("")
    assert module_path_for_test_file(outside, project) is None


def test_abspath_normalises_relative_and_absolute() -> None:
    """AC2: abspath joins relative paths to project, keeps absolute paths."""
    project = Path("/p")
    assert abspath("tests/test_x.py", project) == project / "tests" / "test_x.py"
    assert abspath("/abs/test_y.py", project) == Path("/abs/test_y.py")


def test_module_path_returns_none_when_outside_tests_dir(tmp_path: Path) -> None:
    """AC2: module_path_for_test_file returns None for in-project non-tests paths."""
    project = tmp_path / "p"
    src_file = project / "src" / "axm_audit" / "mod.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text("")
    assert module_path_for_test_file(src_file, project) is None


def test_file_depth_returns_zero_for_path_outside_project(tmp_path: Path) -> None:
    """AC2: file_depth_from_project returns 0 when path is outside project_path."""
    project = tmp_path / "p"
    project.mkdir()
    outside = tmp_path / "elsewhere" / "test_x.py"
    outside.parent.mkdir()
    outside.write_text("")
    assert file_depth_from_project(outside, project) == 0


def test_file_depth_invariant_under_project_path(tmp_path: Path) -> None:
    """AC2: file_depth_from_project depends on relative path, not project depth."""
    project1 = tmp_path / "p1"
    project2 = tmp_path / "deep" / "nest" / "p2"
    f1 = project1 / "tests" / "unit" / "core" / "test_X.py"
    f2 = project2 / "tests" / "unit" / "core" / "test_X.py"
    f1.parent.mkdir(parents=True)
    f2.parent.mkdir(parents=True)
    f1.write_text("")
    f2.write_text("")
    assert file_depth_from_project(f1, project1) == file_depth_from_project(
        f2, project2
    )
