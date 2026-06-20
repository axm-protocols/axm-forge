"""Unit tests for the node structure gold-standard checks."""

from __future__ import annotations

from pathlib import Path

from axm_init.checks.node.structure import (
    check_contributing,
    check_gitignore,
    check_license_file,
    check_lock_file,
    check_readme,
    check_tests_dir,
)


def test_lock_file_present_passes(tmp_path: Path) -> None:
    """A package-lock.json passes the lockfile check."""
    (tmp_path / "package-lock.json").write_text("{}")
    assert check_lock_file(tmp_path).passed is True


def test_pnpm_lock_passes(tmp_path: Path) -> None:
    """A pnpm-lock.yaml also satisfies the lockfile check."""
    (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
    assert check_lock_file(tmp_path).passed is True


def test_lock_file_absent_fails(tmp_path: Path) -> None:
    """No lockfile fails."""
    assert check_lock_file(tmp_path).passed is False


def test_tests_dir_passes(tmp_path: Path) -> None:
    """A tests/ directory satisfies the tests check."""
    (tmp_path / "tests").mkdir()
    assert check_tests_dir(tmp_path).passed is True


def test_colocated_tests_pass(tmp_path: Path) -> None:
    """Colocated *.test.ts files satisfy the tests check."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.test.ts").write_text("test('x', () => {});")
    assert check_tests_dir(tmp_path).passed is True


def test_no_tests_fails(tmp_path: Path) -> None:
    """No tests anywhere fails."""
    (tmp_path / "src").mkdir()
    assert check_tests_dir(tmp_path).passed is False


_README = (
    "# pkg\n## Features\nx\n## Installation\nx\n## Development\nx\n## License\nMIT\n"
)


def test_license_present_passes(tmp_path: Path) -> None:
    """A LICENSE file passes."""
    (tmp_path / "LICENSE").write_text("MIT")
    assert check_license_file(tmp_path).passed is True


def test_license_absent_fails(tmp_path: Path) -> None:
    """No LICENSE fails."""
    assert check_license_file(tmp_path).passed is False


def test_contributing_present_passes(tmp_path: Path) -> None:
    """A CONTRIBUTING.md passes."""
    (tmp_path / "CONTRIBUTING.md").write_text("# Contributing")
    assert check_contributing(tmp_path).passed is True


def test_gitignore_must_ignore_node_modules(tmp_path: Path) -> None:
    """A .gitignore without node_modules fails."""
    (tmp_path / ".gitignore").write_text("dist/\n")
    assert check_gitignore(tmp_path).passed is False
    (tmp_path / ".gitignore").write_text("node_modules/\ndist/\n")
    assert check_gitignore(tmp_path).passed is True


def test_readme_sections(tmp_path: Path) -> None:
    """A README with all required sections passes; a bare one fails."""
    (tmp_path / "README.md").write_text("# pkg\n")
    assert check_readme(tmp_path).passed is False
    (tmp_path / "README.md").write_text(_README)
    assert check_readme(tmp_path).passed is True
