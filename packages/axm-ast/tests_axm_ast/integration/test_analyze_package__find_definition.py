"""Split from ``test_impact.py``."""

from pathlib import Path

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.impact import find_definition


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


class TestFindDefinition:
    """Test symbol definition location."""

    def test_find_function(self, tmp_path: Path) -> None:
        """Finds function in correct module with line."""
        pkg_dir = _make_project(tmp_path)
        pkg = analyze_package(pkg_dir)
        defn = find_definition(pkg, "helper")
        assert defn is not None
        assert "core" in defn["module"]
        assert defn["line"] > 0

    def test_find_class(self, tmp_path: Path) -> None:
        """Finds class definition."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            '"""Pkg."""\nclass Engine:\n    """Engine."""\n    pass\n'
        )
        info = analyze_package(pkg)
        defn = find_definition(info, "Engine")
        assert defn is not None
        assert defn["kind"] == "class"

    def test_not_found(self, tmp_path: Path) -> None:
        """Unknown symbol returns None."""
        pkg_dir = _make_project(tmp_path)
        pkg = analyze_package(pkg_dir)
        defn = find_definition(pkg, "nonexistent")
        assert defn is None
