"""Split from ``test_shared_helpers_io.py``."""

from pathlib import Path

from axm_audit.core.rules.test_quality._shared import current_level_from_path


def test_current_level_from_path_unit(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    test_file = tests_dir / "unit" / "x" / "test_a.py"
    assert current_level_from_path(test_file, tests_dir) == "unit"


def test_current_level_from_path_integration_from_functional(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    test_file = tests_dir / "functional" / "test_x.py"
    assert current_level_from_path(test_file, tests_dir) == "integration"


def test_current_level_from_path_root(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    test_file = tests_dir / "test_root.py"
    assert current_level_from_path(test_file, tests_dir) == "root"
