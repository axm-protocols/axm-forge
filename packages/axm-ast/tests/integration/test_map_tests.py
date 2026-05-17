"""Split from ``test_impact.py``."""

from pathlib import Path

from axm_ast.core.impact import map_tests


def _make_project(tmp_path: Path) -> Path:
    """Create a typical project with init, module, and tests."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        '"""Pkg."""\nfrom .core import helper\n\n__all__ = ["helper"]\n'
    )
    (pkg / "core.py").write_text(
        '"""Core module."""\n'
        "def helper(x: int) -> int:\n"
        '    """Help."""\n'
        "    return x + 1\n"
        "\n"
        "def _private() -> None:\n"
        '    """Private."""\n'
        "    pass\n"
    )
    (pkg / "cli.py").write_text(
        '"""CLI."""\n'
        "def main() -> None:\n"
        '    """Main."""\n'
        "    helper(42)\n"
        "\n"
        "def other() -> None:\n"
        '    """Other."""\n'
        "    helper(99)\n"
    )
    # Tests directory
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_core.py").write_text(
        '"""Test core."""\ndef test_helper() -> None:\n    """Test."""\n    helper(1)\n'
    )
    (tests / "test_cli.py").write_text(
        '"""Test CLI."""\ndef test_main() -> None:\n    """Test."""\n    main()\n'
    )
    return pkg


class TestMapTests:
    """Test test file detection."""

    def test_finds_relevant_tests(self, tmp_path: Path) -> None:
        """Identifies test files that reference the symbol."""
        _make_project(tmp_path)
        test_files = map_tests("helper", tmp_path)
        names = [t.name for t in test_files]
        assert "test_core.py" in names

    def test_no_tests_dir(self, tmp_path: Path) -> None:
        """Graceful when no tests/ exists."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pkg."""\n')
        test_files = map_tests("helper", tmp_path)
        assert test_files == []
