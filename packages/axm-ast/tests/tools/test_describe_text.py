from __future__ import annotations

import re
from pathlib import Path

import pytest

from axm_ast.tools.describe import DescribeTool

AST_PKG = str(Path(__file__).resolve().parents[2] / "src" / "axm_ast")


@pytest.fixture()
def tool() -> DescribeTool:
    return DescribeTool()


# ── Unit tests ───────────────────────────────────────────────────────


def test_toc_has_text(tool: DescribeTool) -> None:
    result = tool.execute(path=AST_PKG, detail="toc")
    assert result.text is not None
    assert result.text.startswith("ast_describe | toc |")


def test_summary_has_text(tool: DescribeTool) -> None:
    result = tool.execute(path=AST_PKG, detail="summary")
    assert result.text is not None
    assert result.text.startswith("ast_describe | summary |")


def test_detailed_has_text(tool: DescribeTool) -> None:
    result = tool.execute(path=AST_PKG, detail="detailed")
    assert result.text is not None
    assert result.text.startswith("ast_describe | detailed |")


def test_compress_has_text(tool: DescribeTool) -> None:
    result = tool.execute(path=AST_PKG, compress=True)
    assert result.text is not None
    assert result.text == result.data["compressed"]


def test_data_unchanged_toc(tool: DescribeTool) -> None:
    result = tool.execute(path=AST_PKG, detail="toc")
    assert isinstance(result.data["modules"], list)
    assert isinstance(result.data["module_count"], int)


def test_data_unchanged_summary(tool: DescribeTool) -> None:
    result = tool.execute(path=AST_PKG, detail="summary")
    assert isinstance(result.data["modules"], list)
    assert isinstance(result.data["module_count"], int)


def test_toc_text_format(tool: DescribeTool) -> None:
    result = tool.execute(path=AST_PKG, detail="toc")
    assert result.text is not None
    lines = result.text.splitlines()
    # Skip the header line
    for line in lines[1:]:
        if line.strip():
            assert re.search(r"\s+\S+\s+\(", line), f"Bad toc line: {line!r}"


def test_summary_strips_def(tool: DescribeTool) -> None:
    result = tool.execute(path=AST_PKG, detail="summary")
    assert result.text is not None
    assert "def " not in result.text


def test_summary_skips_empty(tool: DescribeTool) -> None:
    result = tool.execute(path=AST_PKG, detail="summary")
    assert result.text is not None
    assert "## _version" not in result.text
    assert "## models\n" not in result.text


def test_detailed_has_summaries(tool: DescribeTool) -> None:
    result = tool.execute(path=AST_PKG, detail="detailed")
    assert result.text is not None
    lines_with_comment = [line for line in result.text.splitlines() if "#" in line]
    assert len(lines_with_comment) > 0


# ── Functional tests ─────────────────────────────────────────────────


def test_summary_token_budget(tool: DescribeTool) -> None:
    result = tool.execute(path=AST_PKG, detail="summary")
    assert result.text is not None
    assert len(result.text) < 35000


def test_modules_filter_with_text(tool: DescribeTool) -> None:
    result = tool.execute(path=AST_PKG, detail="summary", modules=["core.cache"])
    assert result.text is not None
    assert "## core.cache" in result.text
    # No other ## headers
    headers = [line for line in result.text.splitlines() if line.startswith("## ")]
    assert len(headers) == 1


# ── Edge cases ───────────────────────────────────────────────────────


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
