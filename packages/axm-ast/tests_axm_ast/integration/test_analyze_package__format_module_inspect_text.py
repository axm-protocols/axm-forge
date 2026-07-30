"""Split from ``test_coverage_gaps.py``."""

from pathlib import Path

from axm_ast.core.analyzer import analyze_package
from axm_ast.formatters import format_module_inspect_text


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    pkg = tmp_path / "mypkg"
    for name, content in files.items():
        fp = pkg / name
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return pkg


class TestFormatModuleInspectText:
    """Cover format_module_inspect_text and related helpers."""

    def test_format_module_inspect(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": (
                    '"""Module docstring."""\n'
                    "def public_fn() -> None:\n"
                    '    """Public."""\n'
                    "    pass\n\n"
                    "def _private_fn() -> None:\n"
                    "    pass\n\n"
                    "class Widget:\n"
                    '    """A widget."""\n'
                    "    def run(self) -> None:\n"
                    "        pass\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        mod = next(m for m in pkg.modules if m.functions or m.classes)
        text = format_module_inspect_text(mod)
        assert "mod.py" in text
        assert "Module docstring" in text
        assert "public_fn" in text
        assert "Widget" in text
        assert "run" in text
