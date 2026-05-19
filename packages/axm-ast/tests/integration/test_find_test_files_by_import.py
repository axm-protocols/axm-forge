"""Drive the import-based test-file heuristic through public ``analyze_impact``.

``analyze_impact`` surfaces the heuristic's matches as the
``test_files_by_import`` field of its :class:`ImpactResult` whenever a
symbol has no direct callers found by name (see
``_add_import_based_tests`` in ``axm_ast.core.impact``).  These tests drive
that code path via the public API instead of reaching into the private helper.
"""

from pathlib import Path

from axm_ast.core.impact import ImpactResult, analyze_impact
from tests.integration._helpers import _make_import_heuristic_project


def _import_tests(result: ImpactResult) -> list[str]:
    """Extract the ``test_files_by_import`` field with safe default."""
    return list(result.get("test_files_by_import", []))


def test_import_heuristic_fires(tmp_path: Path) -> None:
    """Heuristic finds test files importing the symbol's module."""
    pkg = _make_import_heuristic_project(tmp_path)
    # InternalCfg has no callers in the package, so map_tests won't find it
    # by name, but test_models.py imports mypkg.models -> heuristic fires.
    result = analyze_impact(pkg, "InternalCfg", project_root=tmp_path)
    assert "test_models.py" in _import_tests(result)


def test_import_heuristic_scoped_to_tests(tmp_path: Path) -> None:
    """Non-test files importing the module are not included."""
    pkg = _make_import_heuristic_project(tmp_path)
    result = analyze_impact(pkg, "InternalCfg", project_root=tmp_path)
    # helper_script.py is at project root, not in tests/ — must not leak in.
    assert "helper_script.py" not in _import_tests(result)


def test_no_tests_import_module(tmp_path: Path) -> None:
    """Completely untested module yields no ``test_files_by_import`` entry."""
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
    result = analyze_impact(pkg, "nobody", project_root=tmp_path)
    # The field is omitted when there are no matches.
    assert _import_tests(result) == []


def test_wildcard_import_detected(tmp_path: Path) -> None:
    """``from module import *`` is still detected by the import heuristic."""
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text('"""Pkg."""\n')
    (pkg / "utils.py").write_text('"""Utils."""\nclass UnreferencedHelper:\n    pass\n')
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_utils.py").write_text(
        '"""Test utils."""\nfrom mypkg.utils import *\n\n'
        "def test_u() -> None:\n    assert True\n"
    )
    # UnreferencedHelper is never named in test files (only the star import),
    # so map_tests cannot match — the heuristic must pick up test_utils.py.
    result = analyze_impact(pkg, "UnreferencedHelper", project_root=tmp_path)
    assert "test_utils.py" in _import_tests(result)
