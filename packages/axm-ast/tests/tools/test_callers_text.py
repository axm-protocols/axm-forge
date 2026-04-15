from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from axm_ast.tools.callers import CallersTool

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tool() -> CallersTool:
    return CallersTool()


def _make_callsite(
    *, module: str, line: int, context: str | None, call_expression: str = "greet()"
) -> MagicMock:
    cs = MagicMock()
    cs.module = module
    cs.line = line
    cs.context = context
    cs.call_expression = call_expression
    return cs


# ---------------------------------------------------------------------------
# Unit tests — _render_text
# ---------------------------------------------------------------------------


def test_text_header_format() -> None:
    """Header follows pattern: ast_callers | {symbol} | {count} callers."""
    callers = [
        {"module": "mod_a", "line": 1, "context": "foo", "call_expression": "greet()"},
        {"module": "mod_b", "line": 2, "context": "bar", "call_expression": "greet()"},
        {"module": "mod_c", "line": 3, "context": "baz", "call_expression": "greet()"},
    ]
    text = CallersTool._render_text(callers, symbol="greet")
    assert text.startswith("ast_callers | greet | 3 callers")


def test_text_caller_lines() -> None:
    """Each caller rendered as {module}:{line} {context}."""
    callers = [
        {
            "module": "axm_ast.cli",
            "line": 42,
            "context": "run",
            "call_expression": "greet()",
        },
        {
            "module": "axm_ast.tools.search",
            "line": 100,
            "context": "execute",
            "call_expression": "greet()",
        },
    ]
    text = CallersTool._render_text(callers, symbol="greet")
    lines = text.strip().splitlines()
    assert len(lines) == 3  # header + 2 callers
    assert lines[1] == "axm_ast.cli:42 run"
    assert lines[2] == "axm_ast.tools.search:100 execute"


def test_text_strips_src_prefix() -> None:
    """src. prefix stripped from module names."""
    callers = [
        {
            "module": "src.axm_ast.cli",
            "line": 10,
            "context": "main",
            "call_expression": "greet()",
        },
    ]
    text = CallersTool._render_text(callers, symbol="greet")
    lines = text.strip().splitlines()
    assert lines[1].startswith("axm_ast.cli:")


def test_text_none_context_omitted() -> None:
    """When context is None, line is just {module}:{line} with no trailing space."""
    callers = [
        {
            "module": "axm_ast.cli",
            "line": 5,
            "context": None,
            "call_expression": "greet()",
        },
    ]
    text = CallersTool._render_text(callers, symbol="greet")
    lines = text.strip().splitlines()
    assert lines[1] == "axm_ast.cli:5"


def test_text_empty_callers() -> None:
    """Empty callers: just the header line."""
    text = CallersTool._render_text([], symbol="greet")
    assert text == "ast_callers | greet | 0 callers"


def test_text_workspace_prefix() -> None:
    """Workspace cross-package format preserves pkg:: prefix."""
    callers = [
        {
            "module": "axm-ast::axm_ast.cli",
            "line": 70,
            "context": "execute",
            "call_expression": "greet()",
        },
    ]
    text = CallersTool._render_text(callers, symbol="greet")
    lines = text.strip().splitlines()
    assert lines[1].startswith("axm-ast::axm_ast.cli:")


def test_data_unchanged_with_text(tool: CallersTool) -> None:
    """data dict still has callers list and count int when text is set."""
    fake_callers = [
        _make_callsite(module="axm_ast.cli", line=10, context="run"),
    ]
    with (
        patch("axm_ast.tools.callers.Path") as mock_path,
        patch("axm_ast.core.cache.get_package"),
        patch("axm_ast.core.callers.find_callers", return_value=fake_callers),
    ):
        mock_path.return_value.resolve.return_value.is_dir.return_value = True
        result = tool.execute(path="/fake", symbol="greet")

    assert result.success is True
    assert isinstance(result.data["callers"], list)
    assert isinstance(result.data["count"], int)
    assert result.data["count"] == 1
    assert result.text is not None


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


def test_callers_text_on_real_package(tool: CallersTool, tmp_path: object) -> None:
    """execute() returns text starting with ast_callers | and line count matches."""
    sample = str(Path(__file__).resolve().parent.parent.parent)
    result = tool.execute(path=sample, symbol="greet")
    # greet may or may not exist — either way the result should be consistent
    if result.success:
        assert result.text is not None
        assert result.text.startswith("ast_callers |")
        # number of non-header lines == count
        body_lines = result.text.strip().splitlines()[1:]
        assert len(body_lines) == result.data["count"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_error_result_no_text(tool: CallersTool) -> None:
    """Error result (symbol=None) has no text field."""
    result = tool.execute(path=".", symbol=None)
    assert result.success is False
    assert result.text is None


def test_module_without_src_prefix() -> None:
    """Module without src. prefix stays unchanged — no double-strip."""
    callers = [
        {
            "module": "tests.test_callers",
            "line": 20,
            "context": "test_it",
            "call_expression": "greet()",
        },
    ]
    text = CallersTool._render_text(callers, symbol="greet")
    lines = text.strip().splitlines()
    assert lines[1].startswith("tests.test_callers:")


def test_very_long_module_name() -> None:
    """Deeply nested module path — no truncation."""
    long_mod = "axm_ast.tools.very.deeply.nested.module.path"
    callers = [
        {
            "module": long_mod,
            "line": 999,
            "context": "deep_fn",
            "call_expression": "greet()",
        },
    ]
    text = CallersTool._render_text(callers, symbol="greet")
    lines = text.strip().splitlines()
    assert lines[1] == f"{long_mod}:999 deep_fn"
