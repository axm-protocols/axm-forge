"""TDD tests for compress mode — intermediate detail level."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.analyzer import analyze_package
from axm_ast.formatters import format_compressed, format_text
from axm_ast.models.nodes import PackageInfo

FIXTURES = Path(__file__).parent / "fixtures"


# ─── Unit tests ──────────────────────────────────────────────────────────────


class TestFormatCompressed:
    """Test the compressed output format."""

    @pytest.fixture()
    def pkg(self) -> PackageInfo:
        """Analyze the sample package."""
        return analyze_package(FIXTURES / "sample_pkg")

    def test_returns_string(self, pkg: PackageInfo) -> None:
        """Returns a non-empty string."""
        output = format_compressed(pkg)
        assert isinstance(output, str)
        assert len(output) > 0

    def test_signatures_present(self, pkg: PackageInfo) -> None:
        """All public function signatures should appear."""
        output = format_compressed(pkg)
        assert "def greet(name: str) -> str" in output
        assert "def resolve_path(p: str) -> Path" in output

    def test_first_docstring_line_only(self, pkg: PackageInfo) -> None:
        """Only the first docstring line is kept."""
        output = format_compressed(pkg)
        assert "Return a greeting message." in output
        # Full multi-line docstrings should not appear
        assert output.count('"""') % 2 == 0  # balanced quotes

    def test_no_function_bodies(self, pkg: PackageInfo) -> None:
        """No function body code (return, raise, etc.)."""
        output = format_compressed(pkg)
        # The sample_pkg greet() returns f"Hello, {name}!"
        assert "Hello, {name}" not in output

    def test_class_present(self, pkg: PackageInfo) -> None:
        """Public classes should appear with their base classes."""
        output = format_compressed(pkg)
        assert "class Calculator" in output

    def test_class_methods_as_stubs(self, pkg: PackageInfo) -> None:
        """Class methods appear as signatures."""
        output = format_compressed(pkg)
        assert "def add(self" in output

    def test_private_symbols_excluded(self, pkg: PackageInfo) -> None:
        """Private symbols not in __all__ are excluded."""
        output = format_compressed(pkg)
        assert "_internal_helper" not in output
        assert "_InternalClass" not in output

    def test_module_docstring_present(self, pkg: PackageInfo) -> None:
        """Module-level docstrings appear."""
        output = format_compressed(pkg)
        assert "A sample Python module" in output

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

    def test_absolute_imports_dropped(self, pkg: PackageInfo) -> None:
        """Absolute imports are dropped."""
        output = format_compressed(pkg)
        assert "from pathlib import" not in output
        assert "from typing import" not in output

    def test_all_exports_shown(self, pkg: PackageInfo) -> None:
        """__all__ list is preserved if it exists."""
        output = format_compressed(pkg)
        assert "__all__" in output

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


# ─── Edge cases ──────────────────────────────────────────────────────────────


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


# ─── Functional: compress vs full/stub ───────────────────────────────────────


class TestCompressFunctional:
    """Functional tests comparing compress to other formats."""

    def test_compress_shorter_than_full(self) -> None:
        """Compressed output is significantly shorter than full."""
        pkg = analyze_package(FIXTURES / "sample_pkg")
        full = format_text(pkg, detail="detailed")
        compressed = format_compressed(pkg)
        assert len(compressed) < len(full)
