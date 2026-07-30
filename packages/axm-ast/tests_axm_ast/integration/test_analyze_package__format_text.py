"""Split from ``test_coverage_gaps.py``."""

from pathlib import Path

from axm_ast.core.analyzer import analyze_package


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    pkg = tmp_path / "mypkg"
    for name, content in files.items():
        fp = pkg / name
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return pkg


def test_format_fn_text_with_docstring_detailed(tmp_path: Path) -> None:
    """Cover _format_fn_text branch for detailed+docstring."""
    from axm_ast.formatters import format_text

    pkg_path = _make_pkg(
        tmp_path,
        {
            "__init__.py": "",
            "mod.py": (
                '"""Module doc."""\ndef foo() -> None:\n    """Foo doc."""\n    pass\n'
            ),
        },
    )
    pkg = analyze_package(pkg_path)
    text = format_text(pkg, detail="detailed")
    assert "Foo doc" in text


def test_format_text_detailed_with_class_docstring(tmp_path: Path) -> None:
    """Cover _format_cls_text branch for detailed+docstring."""
    from axm_ast.formatters import format_text

    pkg_path = _make_pkg(
        tmp_path,
        {
            "__init__.py": "",
            "mod.py": ('class MyClass:\n    """My class doc."""\n    pass\n'),
        },
    )
    pkg = analyze_package(pkg_path)
    text = format_text(pkg, detail="detailed")
    assert "My class doc" in text
