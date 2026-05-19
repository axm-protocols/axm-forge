"""Split from ``test_coverage_gaps.py``."""

from pathlib import Path

import pytest

from axm_ast.core.analyzer import analyze_package
from axm_ast.formatters import format_compressed


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    pkg = tmp_path / "mypkg"
    for name, content in files.items():
        fp = pkg / name
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return pkg


def test_compress_module_with_docstring(tmp_path: Path) -> None:
    """Cover _compress_module branch for module docstring."""
    from axm_ast.formatters import format_compressed

    pkg_path = _make_pkg(
        tmp_path,
        {
            "__init__.py": "",
            "mod.py": '"""My module summary."""\n\nx = 1\n',
        },
    )
    pkg = analyze_package(pkg_path)
    text = format_compressed(pkg)
    assert "My module summary" in text


class TestCompressClassNoDocstring:
    """Cover formatters line 289-290 (class without docstring → '...')."""

    def test_compress_class_no_docstring_no_methods(self, tmp_path: Path) -> None:
        from axm_ast.formatters import format_compressed

        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": "class Empty:\n    pass\n",
            },
        )
        pkg = analyze_package(pkg_path)
        text = format_compressed(pkg)
        assert "class Empty" in text


class TestFormatCompressedIntegration:
    """Integration-level format tests using tmp_path."""

    @pytest.mark.parametrize(
        ("pkg_name", "files", "expected"),
        [
            pytest.param(
                "relpkg",
                {
                    "__init__.py": '"""Rel pkg."""\n',
                    "core.py": (
                        '"""Core."""\ndef helper() -> None:\n'
                        '    """Help."""\n    pass\n'
                    ),
                    "cli.py": (
                        '"""CLI."""\n'
                        "from . import core\n"
                        "def main() -> None:\n"
                        '    """Main."""\n'
                        "    pass\n"
                    ),
                },
                "from . import core",
                id="relative_imports_kept",
            ),
            pytest.param(
                "nomethod",
                {
                    "__init__.py": (
                        '"""No method."""\nclass Foo:\n    """A class."""\n    pass\n'
                    ),
                },
                "class Foo",
                id="class_no_methods",
            ),
            pytest.param(
                "nodoc",
                {
                    "__init__.py": (
                        '"""No doc."""\ndef bare() -> int:\n    return 42\n'
                    ),
                },
                "def bare() -> int",
                id="no_docstring_function",
            ),
            pytest.param(
                "constonly",
                {
                    "__init__.py": (
                        '"""Constants only."""\nDEBUG = False\nVERSION = \'2.0\'\n'
                    ),
                },
                "Constants only.",
                id="module_with_only_constants",
            ),
        ],
    )
    def test_compressed_output_contains(
        self,
        tmp_path: Path,
        pkg_name: str,
        files: dict[str, str],
        expected: str,
    ) -> None:
        """Compressed formatter preserves the expected signature/literal."""
        pkg_dir = tmp_path / pkg_name
        pkg_dir.mkdir()
        for rel, content in files.items():
            (pkg_dir / rel).write_text(content)
        pkg = analyze_package(pkg_dir)
        output = format_compressed(pkg)
        assert expected in output

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
