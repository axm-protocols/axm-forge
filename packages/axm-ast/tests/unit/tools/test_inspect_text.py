from __future__ import annotations

import json

import pytest

from axm_ast.tools.inspect import InspectTool

PKG_PATH = "."


@pytest.fixture
def tool() -> InspectTool:
    return InspectTool()


# --- Unit tests ---


def test_inspect_function_has_text(tool: InspectTool) -> None:
    """AC1: function symbol returns text with name and signature."""
    result = tool.execute(symbol="search_symbols", path=PKG_PATH)
    assert result.success
    assert result.text is not None
    assert "search_symbols" in result.text


def test_inspect_class_has_text(tool: InspectTool) -> None:
    """AC1: class symbol returns text with class name and bases."""
    result = tool.execute(symbol="PackageInfo", path=PKG_PATH)
    assert result.success
    assert result.text is not None
    assert "PackageInfo" in result.text


def test_inspect_variable_has_text(tool: InspectTool) -> None:
    """AC1: variable symbol returns text containing 'variable'."""
    result = tool.execute(symbol="logger", path=PKG_PATH)
    assert result.success
    assert result.text is not None
    assert "variable" in result.text.lower()


def test_inspect_module_has_text(tool: InspectTool) -> None:
    """AC3: module inspection returns text with 'module' and symbol count."""
    result = tool.execute(symbol="models.nodes", path=PKG_PATH)
    assert result.success
    assert result.text is not None
    assert "module" in result.text.lower()


def test_inspect_dotted_has_text(tool: InspectTool) -> None:
    """AC4: dotted path returns text."""
    result = tool.execute(symbol="PackageInfo.module_names", path=PKG_PATH)
    assert result.success
    assert result.text is not None


def test_inspect_batch_has_text(tool: InspectTool) -> None:
    """AC2: batch inspection returns text with both names, blank-line separated."""
    result = tool.execute(symbols=["search_symbols", "PackageInfo"], path=PKG_PATH)
    assert result.success
    assert result.text is not None
    assert "search_symbols" in result.text
    assert "PackageInfo" in result.text
    assert "\n\n" in result.text


def test_inspect_source_has_text(tool: InspectTool) -> None:
    """AC6: source=True includes fenced code block in text."""
    result = tool.execute(symbol="search_symbols", path=PKG_PATH, source=True)
    assert result.success
    assert result.text is not None
    assert "```python" in result.text


def test_inspect_error_no_text(tool: InspectTool) -> None:
    """AC5: error results do NOT set text."""
    result = tool.execute(symbol="nonexistent_xyz", path=PKG_PATH)
    assert not result.success
    assert result.text is None
    assert result.error is not None


def test_inspect_data_preserved(tool: InspectTool) -> None:
    """AC7: data dict is preserved with symbol key."""
    result = tool.execute(symbol="search_symbols", path=PKG_PATH)
    assert result.success
    assert result.data is not None
    assert "symbol" in result.data
    assert isinstance(result.data["symbol"], dict)


# --- Functional tests ---


def test_text_tokens_less_than_json(tool: InspectTool) -> None:
    """Text representation is more compact than JSON data."""
    result = tool.execute(symbol="search_symbols", path=PKG_PATH)
    assert result.success
    assert result.text is not None
    json_str = json.dumps(result.data)
    assert len(result.text) < len(json_str)


# --- Edge cases ---


def test_batch_with_errors(tool: InspectTool) -> None:
    """Batch with mix of valid and invalid symbols includes both in text."""
    result = tool.execute(symbols=["search_symbols", "nonexistent_xyz"], path=PKG_PATH)
    assert result.success
    assert result.text is not None
    assert "search_symbols" in result.text
    assert "nonexistent" in result.text.lower() or "error" in result.text.lower()


def test_empty_symbol_name(tool: InspectTool) -> None:
    """Empty symbol name returns error with no text."""
    result = tool.execute(symbol="", path=PKG_PATH)
    assert not result.success
    assert result.text is None
