"""Integration tests for axm_audit.core.fix.paths — real-filesystem helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.paths import file_depth_from_project, module_path_for_test_file

pytestmark = pytest.mark.integration


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
