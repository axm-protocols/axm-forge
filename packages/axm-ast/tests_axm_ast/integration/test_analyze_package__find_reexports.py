"""Split from ``test_impact.py``."""

from pathlib import Path

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.impact import find_reexports


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


class TestFindReexports:
    """Test re-export detection."""

    def test_reexport_in_init(self, tmp_path: Path) -> None:
        """Detects re-export in __init__.py via __all__."""
        pkg_dir = _make_project(tmp_path)
        pkg = analyze_package(pkg_dir)
        reexports = find_reexports(pkg, "helper")
        assert len(reexports) >= 1
        assert any("__init__" in r or r.endswith("pkg") for r in reexports)

    def test_no_reexport(self, tmp_path: Path) -> None:
        """Symbol not re-exported returns empty."""
        pkg_dir = _make_project(tmp_path)
        pkg = analyze_package(pkg_dir)
        reexports = find_reexports(pkg, "_private")
        assert reexports == []
