"""Split from ``test_impact.py``."""

from pathlib import Path

from axm_ast.core.impact import _find_test_files_by_import
from tests.integration._helpers import _make_import_heuristic_project


def test_import_heuristic_fires(tmp_path: Path) -> None:
    """Heuristic finds test files importing the symbol's module."""
    _make_import_heuristic_project(tmp_path)
    # UserConfig has no callers in the package, so map_tests won't find it by name
    # but test_models.py imports mypkg.models
    result = _find_test_files_by_import("models", tmp_path)
    names = [p.name for p in result]
    assert "test_models.py" in names


def test_import_heuristic_scoped_to_tests(tmp_path: Path) -> None:
    """Non-test files importing the module are not included."""
    _make_import_heuristic_project(tmp_path)
    result = _find_test_files_by_import("models", tmp_path)
    names = [p.name for p in result]
    # helper_script.py is at project root, not in tests/
    assert "helper_script.py" not in names


def test_no_tests_import_module(tmp_path: Path) -> None:
    """Completely untested module returns empty."""
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text('"""Pkg."""\n')
    (pkg / "orphan.py").write_text(
        '"""Orphan module."""\ndef nobody() -> None:\n    pass\n'
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_other.py").write_text(
        '"""Test other."""\ndef test_x() -> None:\n    assert True\n'
    )
    result = _find_test_files_by_import("orphan", tmp_path)
    assert result == []


def test_wildcard_import_detected(tmp_path: Path) -> None:
    """from module import * is still detected."""
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text('"""Pkg."""\n')
    (pkg / "utils.py").write_text('"""Utils."""\ndef util_fn() -> None:\n    pass\n')
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_utils.py").write_text(
        '"""Test utils."""\nfrom mypkg.utils import *\n\n'
        "def test_u() -> None:\n    assert True\n"
    )
    result = _find_test_files_by_import("utils", tmp_path)
    names = [p.name for p in result]
    assert "test_utils.py" in names
