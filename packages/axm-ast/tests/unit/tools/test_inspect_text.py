from __future__ import annotations

import json
from typing import Any

import pytest

from axm_ast.tools.inspect import InspectTool
from axm_ast.tools.inspect_text import (
    render_batch_text,
    render_class_text,
    render_function_text,
    render_module_text,
    render_symbol_text,
    render_variable_text,
)

PKG_PATH = "."


@pytest.fixture
def tool() -> InspectTool:
    return InspectTool()


# ---------------------------------------------------------------------------
# Fixtures — render_* helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def function_detail_basic() -> dict[str, Any]:
    return {
        "name": "process_data",
        "kind": "function",
        "file": "utils/helpers.py",
        "start_line": 10,
        "end_line": 25,
        "signature": "(items: list[str], *, limit: int = 100) -> int",
        "docstring": "Process a list of data items and return the count.",
        "parameters": [
            {"name": "items", "annotation": "list[str]", "default": None},
            {"name": "limit", "annotation": "int", "default": "100"},
        ],
        "return_type": "int",
    }


@pytest.fixture
def class_detail_basic() -> dict[str, Any]:
    return {
        "name": "ConfigLoader",
        "kind": "class",
        "file": "config/loader.py",
        "start_line": 5,
        "end_line": 50,
        "bases": ["BaseModel"],
        "docstring": "Load and validate configuration files.",
        "methods": ["load", "validate", "dump"],
    }


@pytest.fixture
def variable_detail_annotation() -> dict[str, Any]:
    return {
        "name": "MAX_RETRIES",
        "kind": "variable",
        "file": "constants.py",
        "start_line": 3,
        "end_line": 3,
        "annotation": "int",
    }


@pytest.fixture
def variable_detail_value() -> dict[str, Any]:
    return {
        "name": "DEFAULT_TIMEOUT",
        "kind": "variable",
        "file": "constants.py",
        "start_line": 5,
        "end_line": 5,
        "value_repr": "30",
    }


@pytest.fixture
def module_detail() -> dict[str, Any]:
    return {
        "name": "helpers",
        "kind": "module",
        "file": "utils/helpers.py",
        "docstring": "Utility helper functions.",
        "functions": ["process_data", "validate_input"],
        "classes": ["DataProcessor"],
        "symbol_count": 3,
    }


# ---------------------------------------------------------------------------
# Unit tests — InspectTool.execute() text field
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("symbol", "expected_substring", "case_insensitive"),
    [
        pytest.param("search_symbols", "search_symbols", False, id="function"),
        pytest.param("PackageInfo", "PackageInfo", False, id="class"),
        pytest.param("logger", "variable", True, id="variable"),
        pytest.param("models.nodes", "module", True, id="module"),
        pytest.param("PackageInfo.module_names", None, False, id="dotted"),
    ],
)
def test_inspect_symbol_has_text(
    tool: InspectTool,
    symbol: str,
    expected_substring: str | None,
    case_insensitive: bool,
) -> None:
    """AC1/AC3/AC4: inspect returns text for func/class/var/module/dotted symbols."""
    result = tool.execute(symbol=symbol, path=PKG_PATH)
    assert result.success
    assert result.text is not None
    if expected_substring is not None:
        haystack = result.text.lower() if case_insensitive else result.text
        needle = expected_substring.lower() if case_insensitive else expected_substring
        assert needle in haystack


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


# ---------------------------------------------------------------------------
# Unit tests — render_function_text
# ---------------------------------------------------------------------------


def test_render_function_text_basic(function_detail_basic: dict[str, Any]) -> None:
    result = render_function_text(function_detail_basic)
    assert "process_data" in result
    assert "utils/helpers.py:10-25" in result
    assert "(items: list[str], *, limit: int = 100) -> int" in result
    assert "Process a list of data items" in result
    assert "Params:" in result
    assert "items: list[str]" in result
    assert "limit: int =100" in result
    assert "Returns:" in result or "returns" in result.lower()
    assert "int" in result


def test_render_function_text_with_source(
    function_detail_basic: dict[str, Any],
) -> None:
    function_detail_basic["source"] = (
        "def process_data(items, *, limit=100):\n    return len(items)"
    )
    result = render_function_text(function_detail_basic)
    assert "```python" in result
    assert "def process_data" in result
    assert "```" in result.split("```python")[1]


def test_render_function_text_no_docstring(
    function_detail_basic: dict[str, Any],
) -> None:
    del function_detail_basic["docstring"]
    result = render_function_text(function_detail_basic)
    assert "process_data" in result
    assert "utils/helpers.py:10-25" in result
    # Should not have an empty docstring section
    lines = result.strip().splitlines()
    assert all(line.strip() != "" or idx == 0 for idx, line in enumerate(lines))


def test_render_function_text_no_parameters() -> None:
    detail = {
        "name": "get_version",
        "kind": "function",
        "file": "version.py",
        "start_line": 1,
        "end_line": 3,
        "signature": "() -> str",
        "return_type": "str",
    }
    result = render_function_text(detail)
    assert "get_version" in result
    assert "Params:" not in result


def test_render_function_text_missing_keys() -> None:
    """Detail with only name + file renders header only, no crash."""
    detail = {
        "name": "bare_func",
        "kind": "function",
        "file": "mod.py",
        "start_line": 1,
        "end_line": 1,
    }
    result = render_function_text(detail)
    assert "bare_func" in result
    assert "mod.py" in result


# ---------------------------------------------------------------------------
# Unit tests — render_class_text
# ---------------------------------------------------------------------------


def test_render_class_text_basic(class_detail_basic: dict[str, Any]) -> None:
    result = render_class_text(class_detail_basic)
    assert "ConfigLoader" in result
    assert "(BaseModel)" in result
    assert "config/loader.py:5-50" in result
    assert "Load and validate configuration" in result
    assert "load" in result
    assert "validate" in result
    assert "dump" in result


def test_render_class_text_no_bases(class_detail_basic: dict[str, Any]) -> None:
    class_detail_basic["bases"] = []
    result = render_class_text(class_detail_basic)
    assert "ConfigLoader" in result
    # No parenthesized suffix when bases is empty
    assert "()" not in result


def test_render_class_text_with_source(class_detail_basic: dict[str, Any]) -> None:
    class_detail_basic["source"] = "class ConfigLoader(BaseModel):\n    pass"
    result = render_class_text(class_detail_basic)
    assert "```python" in result
    assert "class ConfigLoader" in result


def test_render_class_text_missing_keys() -> None:
    detail = {
        "name": "EmptyClass",
        "kind": "class",
        "file": "empty.py",
        "start_line": 1,
        "end_line": 2,
    }
    result = render_class_text(detail)
    assert "EmptyClass" in result
    assert "empty.py" in result


# ---------------------------------------------------------------------------
# Unit tests — render_variable_text
# ---------------------------------------------------------------------------


def test_render_variable_text_with_annotation(
    variable_detail_annotation: dict[str, Any],
) -> None:
    result = render_variable_text(variable_detail_annotation)
    assert "MAX_RETRIES" in result
    assert ": int" in result
    assert "constants.py" in result


def test_render_variable_text_with_value(variable_detail_value: dict[str, Any]) -> None:
    result = render_variable_text(variable_detail_value)
    assert "DEFAULT_TIMEOUT" in result
    assert "= 30" in result


def test_render_variable_text_missing_keys() -> None:
    detail = {
        "name": "UNKNOWN",
        "kind": "variable",
        "file": "x.py",
        "start_line": 1,
        "end_line": 1,
    }
    result = render_variable_text(detail)
    assert "UNKNOWN" in result
    assert "x.py" in result


# ---------------------------------------------------------------------------
# Unit tests — render_module_text
# ---------------------------------------------------------------------------


def test_render_module_text(module_detail: dict[str, Any]) -> None:
    result = render_module_text(module_detail)
    assert "helpers" in result
    assert "module" in result
    assert "3 symbols" in result
    assert "process_data" in result
    assert "validate_input" in result
    assert "DataProcessor" in result


# ---------------------------------------------------------------------------
# Unit tests — render_symbol_text dispatcher
# ---------------------------------------------------------------------------


def test_render_symbol_text_dispatches(
    function_detail_basic: dict[str, Any],
    class_detail_basic: dict[str, Any],
    variable_detail_annotation: dict[str, Any],
) -> None:
    func_result = render_symbol_text(function_detail_basic)
    assert func_result == render_function_text(function_detail_basic)

    class_result = render_symbol_text(class_detail_basic)
    assert class_result == render_class_text(class_detail_basic)

    var_result = render_symbol_text(variable_detail_annotation)
    assert var_result == render_variable_text(variable_detail_annotation)


def test_render_symbol_text_dispatches_module(module_detail: dict[str, Any]) -> None:
    result = render_symbol_text(module_detail)
    assert result == render_module_text(module_detail)


# ---------------------------------------------------------------------------
# Unit tests — render_batch_text
# ---------------------------------------------------------------------------


def test_render_batch_text_mixed(
    function_detail_basic: dict[str, Any],
    class_detail_basic: dict[str, Any],
) -> None:
    error_entry = {"name": "broken_sym", "error": "Symbol not found"}
    items = [function_detail_basic, class_detail_basic, error_entry]
    result = render_batch_text(items)
    assert "process_data" in result
    assert "ConfigLoader" in result
    assert "broken_sym" in result
    assert "⚠" in result  # ⚠ character
    # Entries separated by blank lines
    parts = result.split("\n\n")
    assert len(parts) >= 3


def test_render_batch_text_empty() -> None:
    result = render_batch_text([])
    assert result == ""


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


def test_text_tokens_less_than_json(tool: InspectTool) -> None:
    """Text representation is more compact than JSON data."""
    result = tool.execute(symbol="search_symbols", path=PKG_PATH)
    assert result.success
    assert result.text is not None
    json_str = json.dumps(result.data)
    assert len(result.text) < len(json_str)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


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


def test_render_function_text_long_docstring() -> None:
    long_doc = "A" * 600
    detail = {
        "name": "wordy",
        "kind": "function",
        "file": "wordy.py",
        "start_line": 1,
        "end_line": 10,
        "signature": "() -> None",
        "docstring": long_doc,
    }
    result = render_function_text(detail)
    # Docstring should be truncated — rendered portion should be much shorter
    # than original 600 chars. Allow up to ~210 for truncation boundary + ellipsis.
    doc_lines = [line for line in result.splitlines() if "A" * 50 in line]
    for line in doc_lines:
        assert len(line) <= 250


def test_render_function_text_docstring_double_newline() -> None:
    detail = {
        "name": "multi_para",
        "kind": "function",
        "file": "mp.py",
        "start_line": 1,
        "end_line": 5,
        "signature": "() -> None",
        "docstring": "First paragraph.\n\nSecond paragraph with more detail.",
    }
    result = render_function_text(detail)
    assert "First paragraph." in result
    # Second paragraph should be truncated away
    assert "Second paragraph" not in result
