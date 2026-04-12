from __future__ import annotations

import json
import re
from typing import Any

import pytest

from axm_ast.tools.inspect import InspectTool

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tool() -> InspectTool:
    return InspectTool()


# Re-use rich_pkg from conftest / test_inspect
# (provides a real package with functions, classes, variables, modules)


# ---------------------------------------------------------------------------
# Token ceilings (word-count proxy, ~1.5x measured values)
# ---------------------------------------------------------------------------

MODE_CEILINGS: dict[str, int] = {
    "function": 200,
    "class": 50,
    "variable": 25,
    "module": 100,
    "dotted": 45,
    "batch": 300,
    "source": 700,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _execute_mode(
    tool: InspectTool, rich_pkg: str, mode: str
) -> tuple[str, dict[str, Any]]:
    """Execute inspect for a given mode and return (text, data)."""
    match mode:
        case "function":
            r = tool.execute(path=rich_pkg, symbol="greet")
        case "class":
            r = tool.execute(path=rich_pkg, symbol="Greeter")
        case "variable":
            r = tool.execute(path=rich_pkg, symbol="VERSION")
        case "module":
            r = tool.execute(path=rich_pkg, symbol="rich_mod")
        case "dotted":
            r = tool.execute(path=rich_pkg, symbol="Greeter.say_hello")
        case "batch":
            r = tool.execute(path=rich_pkg, symbols=["greet", "Greeter", "VERSION"])
        case "source":
            r = tool.execute(path=rich_pkg, symbol="greet", source=True)
        case _:
            pytest.fail(f"Unknown mode: {mode}")

    assert r.success, f"execute failed for mode={mode}: {r.error}"
    assert r.text is not None
    return r.text, r.data


# ---------------------------------------------------------------------------
# AC2: Comparative — text shorter than JSON for every mode
# ---------------------------------------------------------------------------

ALL_MODES = ["function", "class", "variable", "module", "dotted", "batch", "source"]


@pytest.mark.parametrize("mode", ALL_MODES)
def test_text_shorter_than_json(tool: InspectTool, rich_pkg: str, mode: str) -> None:
    text, data = _execute_mode(tool, rich_pkg, mode)
    json_len = len(json.dumps(data))
    text_len = len(text)
    assert text_len < json_len, (
        f"mode={mode}: text ({text_len}) should be shorter than JSON ({json_len})"
    )


# ---------------------------------------------------------------------------
# AC1: Token ceiling per mode
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ALL_MODES)
def test_text_word_count_ceiling(tool: InspectTool, rich_pkg: str, mode: str) -> None:
    text, _ = _execute_mode(tool, rich_pkg, mode)
    word_count = len(text.split())
    ceiling = MODE_CEILINGS[mode]
    assert word_count < ceiling, (
        f"mode={mode}: word count {word_count} exceeds ceiling {ceiling}"
    )


# ---------------------------------------------------------------------------
# AC3: Header pattern — first line structure
# ---------------------------------------------------------------------------

# Standard header: "symbol_name  file.py:10-25"
HEADER_RANGE_RE = re.compile(r"^\S+\s+\S+:\d+-\d+")
# Variable header may use single line number: "VERSION  file.py:3"
HEADER_VAR_RE = re.compile(r"^\S+\s+\S+:\d+\s*")


HEADER_MOD_RE = re.compile(r"^\S+\s+\S+\s+module")


@pytest.mark.parametrize(
    "mode",
    ["function", "class", "dotted", "batch", "source"],
)
def test_header_pattern(tool: InspectTool, rich_pkg: str, mode: str) -> None:
    text, _ = _execute_mode(tool, rich_pkg, mode)
    first_line = text.split("\n", 1)[0]
    assert HEADER_RANGE_RE.match(first_line), (
        f"mode={mode}: first line does not match header pattern: {first_line!r}"
    )


def test_header_pattern_module(tool: InspectTool, rich_pkg: str) -> None:
    text, _ = _execute_mode(tool, rich_pkg, "module")
    first_line = text.split("\n", 1)[0]
    assert HEADER_MOD_RE.match(first_line), (
        f"module header does not match pattern: {first_line!r}"
    )


def test_header_pattern_variable(tool: InspectTool, rich_pkg: str) -> None:
    text, _ = _execute_mode(tool, rich_pkg, "variable")
    first_line = text.split("\n", 1)[0]
    assert HEADER_VAR_RE.match(first_line), (
        f"variable header does not match pattern: {first_line!r}"
    )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_source_mode_word_count_ceiling(tool: InspectTool, rich_pkg: str) -> None:
    """Source mode on a function must stay under 700 words."""
    text, _ = _execute_mode(tool, rich_pkg, "source")
    word_count = len(text.split())
    assert word_count < 700, f"source mode word count {word_count} >= 700"


def test_batch_error_mixed(tool: InspectTool, rich_pkg: str) -> None:
    """Batch with 2 valid + 1 invalid symbol: text still shorter than JSON."""
    r = tool.execute(path=rich_pkg, symbols=["greet", "Greeter", "DOES_NOT_EXIST_XYZ"])
    assert r.success
    assert r.text is not None
    text_len = len(r.text)
    json_len = len(json.dumps(r.data))
    assert text_len < json_len, (
        f"batch mixed: text ({text_len}) should be shorter than JSON ({json_len})"
    )
