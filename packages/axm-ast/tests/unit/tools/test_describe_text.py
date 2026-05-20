from __future__ import annotations

import re
from pathlib import Path

import pytest

from axm_ast.tools.describe import DescribeTool

AST_PKG = str(Path(__file__).resolve().parents[3] / "src" / "axm_ast")


@pytest.fixture()
def tool() -> DescribeTool:
    return DescribeTool()


# ── Unit tests ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "detail",
    [
        pytest.param("toc", id="toc_has_text"),
        pytest.param("summary", id="summary_has_text"),
        pytest.param("detailed", id="detailed_has_text"),
    ],
)
def test_detail_has_text(tool: DescribeTool, detail: str) -> None:
    """Every detail mode emits a text header prefixed with 'ast_describe'."""
    # Expected prefix: 'ast_describe | <detail> |'
    result = tool.execute(path=AST_PKG, detail=detail)
    assert result.text is not None
    assert result.text.startswith(f"ast_describe | {detail} |")


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


def test_modules_filter_with_text(tool: DescribeTool) -> None:
    result = tool.execute(path=AST_PKG, detail="summary", modules=["core.cache"])
    assert result.text is not None
    assert "## core.cache" in result.text
    # No other ## headers
    headers = [line for line in result.text.splitlines() if line.startswith("## ")]
    assert len(headers) == 1
