"""Split from ``test_paths.py``."""

from pathlib import Path

from axm_audit.core.fix.paths import file_depth_from_project


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
