"""Split from ``test_coverage_gaps.py``."""

from pathlib import Path

from axm_ast.core.analyzer import analyze_package
from axm_ast.formatters import format_symbol_text


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    pkg = tmp_path / "mypkg"
    for name, content in files.items():
        fp = pkg / name
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return pkg


class TestFormatSymbolText:
    """Cover _format_function_text, _format_class_text, format_symbol_text."""

    def test_format_function_text(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": (
                    "def greet(name: str) -> str:\n"
                    '    """Say hello.\n\n'
                    "    Raises:\n"
                    "        ValueError: If name is empty.\n\n"
                    "    Examples:\n"
                    "        >>> greet('world')\n"
                    "        'hello world'\n"
                    '    """\n'
                    "    return f'hello {name}'\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        mod = next(m for m in pkg.modules if m.functions)
        fn = mod.functions[0]
        text = format_symbol_text(fn)
        assert "greet" in text
        assert "Say hello" in text
        assert "ValueError" in text

    def test_format_class_text(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": (
                    "class Animal(object):\n"
                    '    """A base animal."""\n'
                    "    def speak(self) -> str:\n"
                    '        """Make sound."""\n'
                    "        return '...'\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        mod = next(m for m in pkg.modules if m.classes)
        cls = mod.classes[0]
        text = format_symbol_text(cls)
        assert "Animal" in text
        assert "object" in text
        assert "speak" in text
