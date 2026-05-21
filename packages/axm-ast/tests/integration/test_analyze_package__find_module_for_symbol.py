"""Split from ``test_function_info__module_info.py``."""

from pathlib import Path

from axm_ast.core.analyzer import analyze_package, find_module_for_symbol


def test_find_source_module_by_symbol(tmp_path: Path) -> None:
    """PackageInfo with known function → public lookup returns its ModuleInfo."""
    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    handler_dir = pkg_dir / "core"
    handler_dir.mkdir()
    (handler_dir / "__init__.py").write_text("")
    handler_py = handler_dir / "handler.py"
    handler_py.write_text("def process(): pass\n")

    pkg = analyze_package(pkg_dir)
    result = find_module_for_symbol(pkg, "process")
    assert result is not None
    assert result.path == handler_py.resolve()
