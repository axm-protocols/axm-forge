"""Integration tests for compress mode — real filesystem fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.analyzer import analyze_package
from axm_ast.formatters import format_compressed

pytestmark = pytest.mark.integration


class TestFormatCompressedIntegration:
    """Integration-level format tests using tmp_path."""

    def test_relative_imports_kept(self, tmp_path: Path) -> None:
        """Public relative imports are preserved."""
        pkg_dir = tmp_path / "relpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text('"""Rel pkg."""\n')
        (pkg_dir / "core.py").write_text(
            '"""Core."""\ndef helper() -> None:\n    """Help."""\n    pass\n'
        )
        (pkg_dir / "cli.py").write_text(
            '"""CLI."""\n'
            "from . import core\n"
            "def main() -> None:\n"
            '    """Main."""\n'
            "    pass\n"
        )
        pkg = analyze_package(pkg_dir)
        output = format_compressed(pkg)
        assert "from . import core" in output

    def test_constants_preserved(self, tmp_path: Path) -> None:
        """Module-level constants are preserved."""
        pkg_dir = tmp_path / "constpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Const pkg."""\n'
            "MAX_RETRIES: int = 3\n"
            "VERSION = '1.0.0'\n"
            "def foo() -> None:\n"
            '    """Foo."""\n'
            "    pass\n"
        )
        pkg = analyze_package(pkg_dir)
        output = format_compressed(pkg)
        assert "MAX_RETRIES" in output or "VERSION" in output

    def test_class_no_methods(self, tmp_path: Path) -> None:
        """Class with no methods renders as 'class Foo: ...'."""
        pkg_dir = tmp_path / "nomethod"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""No method."""\nclass Foo:\n    """A class."""\n    pass\n'
        )
        pkg = analyze_package(pkg_dir)
        output = format_compressed(pkg)
        assert "class Foo" in output


class TestCompressEdgeCases:
    """Edge cases for compress mode."""

    def test_no_docstring_function(self, tmp_path: Path) -> None:
        """Function without docstring still shows signature."""
        pkg_dir = tmp_path / "nodoc"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""No doc."""\ndef bare() -> int:\n    return 42\n'
        )
        pkg = analyze_package(pkg_dir)
        output = format_compressed(pkg)
        assert "def bare() -> int" in output

    def test_module_with_only_constants(self, tmp_path: Path) -> None:
        """Module with only constants, no functions."""
        pkg_dir = tmp_path / "constonly"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Constants only."""\nDEBUG = False\nVERSION = \'2.0\'\n'
        )
        pkg = analyze_package(pkg_dir)
        output = format_compressed(pkg)
        assert "Constants only." in output
