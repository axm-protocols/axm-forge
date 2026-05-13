from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.tools.describe import DescribeTool


@pytest.fixture()
def tool() -> DescribeTool:
    return DescribeTool()


def test_empty_package(tool: DescribeTool, tmp_path: Path) -> None:
    pkg_dir = tmp_path / "empty_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").touch()
    result = tool.execute(path=str(pkg_dir), detail="summary")
    assert result.success
    assert result.text is not None
    assert result.text.startswith("ast_describe | summary | 1 modules")


def test_module_with_only_classes(tool: DescribeTool, tmp_path: Path) -> None:
    pkg_dir = tmp_path / "cls_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").touch()
    (pkg_dir / "shapes.py").write_text(
        "class Circle:\n    pass\n\nclass Square:\n    pass\n"
    )
    result = tool.execute(path=str(pkg_dir), detail="summary")
    assert result.success
    assert result.text is not None
    assert "Circle" in result.text or "Square" in result.text


def test_no_docstring_on_module(tool: DescribeTool, tmp_path: Path) -> None:
    pkg_dir = tmp_path / "nodoc_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").touch()
    (pkg_dir / "bare.py").write_text("def hello(): pass\n")
    result = tool.execute(path=str(pkg_dir), detail="detailed")
    assert result.success
    assert result.text is not None
    # Header should have module name without em-dash suffix
    for line in result.text.splitlines():
        if line.startswith("## ") and "bare" in line:
            assert "\u2014" not in line
            break


def test_very_long_signature(tool: DescribeTool, tmp_path: Path) -> None:
    pkg_dir = tmp_path / "long_sig_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").touch()
    params = ", ".join(f"p{i}: int = 0" for i in range(12))
    (pkg_dir / "wide.py").write_text(f"def big_func({params}): pass\n")
    result = tool.execute(path=str(pkg_dir), detail="summary")
    assert result.success
    assert result.text is not None
    # Full signature on one line (no wrapping)
    sig_lines = [line for line in result.text.splitlines() if "big_func" in line]
    assert len(sig_lines) == 1
    assert "p11" in sig_lines[0]
