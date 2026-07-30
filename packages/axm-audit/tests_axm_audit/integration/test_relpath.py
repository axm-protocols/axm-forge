"""Split from ``test_pyramid_level_render.py``."""

from pathlib import Path

from axm_audit.core.rules.test_quality.pyramid_level import relpath


def test_relpath_relativizes_inside_project(tmp_path: Path) -> None:
    abs_path = tmp_path / "tests" / "unit" / "test_foo.py"
    assert relpath(str(abs_path), tmp_path) == "tests/unit/test_foo.py"


def test_relpath_falls_back_to_absolute_when_outside(tmp_path: Path) -> None:
    outside = "/some/other/place/test_foo.py"
    assert relpath(outside, tmp_path) == outside
