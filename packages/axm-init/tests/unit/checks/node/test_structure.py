"""Unit tests for the node structure gold-standard checks."""

from __future__ import annotations

from pathlib import Path

from axm_init.checks.node.structure import (
    check_contributing,
    check_gitignore,
    check_license_file,
    check_readme,
)

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
