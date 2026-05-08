from __future__ import annotations

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


class TestFileExistsRuleIO:
    """Integration tests for FileExistsRule (real filesystem)."""

    @pytest.mark.parametrize(
        ("create", "expected_passed", "expected_substr"),
        [
            pytest.param(True, True, "exists", id="exists"),
            pytest.param(False, False, "not found", id="missing"),
        ],
    )
    def test_file_presence(
        self,
        tmp_path: Path,
        create: bool,
        expected_passed: bool,
        expected_substr: str,
    ) -> None:
        """Existing file passes; missing file fails."""
        from axm_audit.core.rules.structure import FileExistsRule

        if create:
            (tmp_path / "README.md").write_text("# Hello")

        rule = FileExistsRule(file_name="README.md")
        result = rule.check(tmp_path)

        assert result.passed is expected_passed
        assert expected_substr in result.message


class TestDirectoryExistsRuleIO:
    """Integration tests for DirectoryExistsRule (real filesystem)."""

    @pytest.mark.parametrize(
        ("create", "expected_passed", "expected_substr"),
        [
            pytest.param(True, True, "exists", id="exists"),
            pytest.param(False, False, "not found", id="missing"),
        ],
    )
    def test_directory_presence(
        self,
        tmp_path: Path,
        create: bool,
        expected_passed: bool,
        expected_substr: str,
    ) -> None:
        """Existing directory passes; missing directory fails."""
        from axm_audit.core.rules.structure import DirectoryExistsRule

        if create:
            (tmp_path / "src").mkdir()

        rule = DirectoryExistsRule(dir_name="src")
        result = rule.check(tmp_path)

        assert result.passed is expected_passed
        assert expected_substr in result.message
