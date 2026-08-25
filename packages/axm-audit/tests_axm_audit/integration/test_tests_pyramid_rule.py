from __future__ import annotations

import re
import textwrap
from pathlib import Path

import pytest

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


def test_pyramid_passes_with_all_dirs(tmp_path: Path) -> None:
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


@pytest.mark.parametrize(
    ("present_dirs", "expected_missing"),
    [
        pytest.param(
            ("tests/integration", "tests/e2e"),
            "tests/unit",
            id="missing_unit",
        ),
        pytest.param(
            ("tests/unit", "tests/e2e"),
            "tests/integration",
            id="missing_integration",
        ),
        pytest.param(
            ("tests/unit", "tests/integration"),
            "tests/e2e",
            id="missing_e2e_selfcontained",
        ),
    ],
)
def test_pyramid_fails_when_dir_missing(
    tmp_path: Path,
    present_dirs: tuple[str, ...],
    expected_missing: str,
) -> None:
    project = _make_project(
        tmp_path,
        pyproject=PYPROJECT_SELFCONTAINED_WITH_MARKERS,
        dirs=present_dirs,
    )
    result = TestsPyramidRule().check(project)
    assert result.passed is False
    assert result.fix_hint is not None
    assert expected_missing in result.fix_hint


def test_pyramid_fails_when_markers_missing(tmp_path: Path) -> None:
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


def test_pyramid_library_allows_no_e2e(tmp_path: Path) -> None:
    project = _make_project(
        tmp_path,
        pyproject=PYPROJECT_LIBRARY,
        dirs=("tests/unit", "tests/integration"),
    )
    result = TestsPyramidRule().check(project)
    assert result.passed is True


def test_pyramid_fails_when_tests_dir_missing(tmp_path: Path) -> None:
    project = _make_project(
        tmp_path,
        pyproject=PYPROJECT_SELFCONTAINED_WITH_MARKERS,
        dirs=(),
    )
    result = TestsPyramidRule().check(project)
    assert result.passed is False
    assert "tests" in (result.message or "").lower()


PYPROJECT_NAMESPACED = textwrap.dedent(
    """
    [project]
    name = "pkg"
    version = "0.1.0"

    [project.scripts]
    pkg = "pkg.cli:main"

    [tool.pytest.ini_options]
    testpaths = ["tests_pkg"]
    markers = [
        "integration: integration tests",
        "e2e: end-to-end tests",
    ]
    """
).strip()


def _make_namespaced_pyramid_project(
    tmp_path: Path, *, tiers: tuple[str, ...], root: str = "tests_pkg"
) -> Path:
    (tmp_path / "pyproject.toml").write_text(PYPROJECT_NAMESPACED)
    for tier in tiers:
        d = tmp_path / root / tier
        d.mkdir(parents=True, exist_ok=True)
        (d / f"test_{tier}.py").write_text("def test_placeholder(): pass\n")
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True, exist_ok=True)
    (src / "__init__.py").write_text("")
    (src / "core.py").write_text("def core():\n    return 1\n")
    return tmp_path


@pytest.mark.integration
def test_pyramid_accepts_full_namespaced_suite(tmp_path: Path) -> None:
    """AC1: complete namespaced suite (testpaths) yields no missing-dir finding."""
    project = _make_namespaced_pyramid_project(
        tmp_path, tiers=("unit", "integration", "e2e")
    )
    result = TestsPyramidRule().check(project)
    assert result.passed is True


@pytest.mark.integration
def test_pyramid_diagnostic_rooted_at_namespaced_suite(tmp_path: Path) -> None:
    """AC2: diagnostic dir paths are first-segment-rooted at the namespaced suite."""
    project = _make_namespaced_pyramid_project(tmp_path, tiers=("unit", "integration"))
    result = TestsPyramidRule().check(project)
    assert result.passed is False
    blob = f"{result.message or ''} {result.fix_hint or ''}"
    cited = [tok for tok in re.split(r"[\s,]+", blob) if "/" in tok]
    assert cited
    for tok in cited:
        parts = Path(tok).parts
        assert parts[0] == "tests_pkg", tok
        assert "tests" not in parts, tok
