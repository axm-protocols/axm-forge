from __future__ import annotations

import textwrap
from pathlib import Path

from axm_audit.core.rules.structure import TestsPyramidRule

__all__ = []


PYPROJECT_SELFCONTAINED_WITH_MARKERS = textwrap.dedent(
    """
    [project]
    name = "pkg"
    version = "0.1.0"

    [project.scripts]
    pkg = "pkg.cli:main"

    [tool.pytest.ini_options]
    markers = [
        "integration: integration tests",
        "e2e: end-to-end tests",
    ]
    """
).strip()


PYPROJECT_SELFCONTAINED_NO_MARKERS = textwrap.dedent(
    """
    [project]
    name = "pkg"
    version = "0.1.0"

    [project.scripts]
    pkg = "pkg.cli:main"
    """
).strip()


PYPROJECT_LIBRARY = textwrap.dedent(
    """
    [project]
    name = "pkg"
    version = "0.1.0"

    [tool.pytest.ini_options]
    markers = [
        "integration: integration tests",
    ]
    """
).strip()


def _make_project(
    tmp_path: Path,
    *,
    pyproject: str,
    dirs: tuple[str, ...] = (),
    src_files: dict[str, str] | None = None,
) -> Path:
    (tmp_path / "pyproject.toml").write_text(pyproject)
    for d in dirs:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True, exist_ok=True)
    (src / "__init__.py").write_text("")
    if src_files:
        for name, content in src_files.items():
            (src / name).write_text(content)
    return tmp_path


def test_tests_pyramid_passes_with_all_dirs(tmp_path: Path) -> None:
    project = _make_project(
        tmp_path,
        pyproject=PYPROJECT_SELFCONTAINED_WITH_MARKERS,
        dirs=("tests/unit", "tests/integration", "tests/e2e"),
    )
    result = TestsPyramidRule().check(project)
    assert result.passed is True
    assert "unit" in result.message
    assert "integration" in result.message
    assert "e2e" in result.message


def test_tests_pyramid_fails_missing_unit(tmp_path: Path) -> None:
    project = _make_project(
        tmp_path,
        pyproject=PYPROJECT_SELFCONTAINED_WITH_MARKERS,
        dirs=("tests/integration", "tests/e2e"),
    )
    result = TestsPyramidRule().check(project)
    assert result.passed is False
    assert result.fix_hint is not None
    assert "tests/unit" in result.fix_hint


def test_tests_pyramid_fails_missing_integration(tmp_path: Path) -> None:
    project = _make_project(
        tmp_path,
        pyproject=PYPROJECT_SELFCONTAINED_WITH_MARKERS,
        dirs=("tests/unit", "tests/e2e"),
    )
    result = TestsPyramidRule().check(project)
    assert result.passed is False
    assert result.fix_hint is not None
    assert "tests/integration" in result.fix_hint


def test_tests_pyramid_fails_missing_e2e_selfcontained(tmp_path: Path) -> None:
    project = _make_project(
        tmp_path,
        pyproject=PYPROJECT_SELFCONTAINED_WITH_MARKERS,
        dirs=("tests/unit", "tests/integration"),
    )
    result = TestsPyramidRule().check(project)
    assert result.passed is False
    assert result.fix_hint is not None
    assert "tests/e2e" in result.fix_hint


def test_tests_pyramid_fails_missing_markers(tmp_path: Path) -> None:
    project = _make_project(
        tmp_path,
        pyproject=PYPROJECT_SELFCONTAINED_NO_MARKERS,
        dirs=("tests/unit", "tests/integration", "tests/e2e"),
    )
    result = TestsPyramidRule().check(project)
    assert result.passed is False
    text = (result.message or "") + " " + (result.fix_hint or "")
    assert "integration" in text
    assert "e2e" in text


def test_tests_pyramid_library_allows_no_e2e(tmp_path: Path) -> None:
    project = _make_project(
        tmp_path,
        pyproject=PYPROJECT_LIBRARY,
        dirs=("tests/unit", "tests/integration"),
    )
    result = TestsPyramidRule().check(project)
    assert result.passed is True


def test_tests_pyramid_fails_no_tests_dir(tmp_path: Path) -> None:
    project = _make_project(
        tmp_path,
        pyproject=PYPROJECT_SELFCONTAINED_WITH_MARKERS,
        dirs=(),
    )
    result = TestsPyramidRule().check(project)
    assert result.passed is False
    assert "tests" in (result.message or "").lower()
