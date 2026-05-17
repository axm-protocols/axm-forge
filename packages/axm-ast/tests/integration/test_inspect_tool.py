from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from axm_ast.tools.inspect import InspectTool
from tests.integration._helpers import _assert_tool_result

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


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    pkg = tmp_path / "mypkg"
    for name, content in files.items():
        fp = pkg / name
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return pkg


@pytest.fixture()
def tool__from_inspect_tool() -> InspectTool:
    """Provide a fresh InspectTool instance."""
    return InspectTool()


def test_inspect_tool_exception(tmp_path: Path, mocker: MagicMock) -> None:
    from axm_ast.tools.inspect import InspectTool

    pkg = _make_pkg(tmp_path, {"__init__.py": ""})
    mocker.patch(
        "axm_ast.core.cache.get_package",
        side_effect=RuntimeError("inspect boom"),
    )
    result = InspectTool().execute(path=str(pkg), symbol="foo")
    assert result.success is False
    assert "inspect boom" in (result.error or "")


class TestInspectToolGaps:
    """Cover tools/inspect.py lines 338, 350, 357-358, 439, 461-462."""

    def test_inspect_text_format_function(self, tmp_path: Path) -> None:
        from axm_ast.tools.inspect import InspectTool

        pkg = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": "def hello() -> str:\n"
                '    """Say hello."""\n'
                "    return 'hi'\n",
            },
        )
        result = InspectTool().execute(path=str(pkg), symbol="hello", format="text")
        assert result.success is True

    def test_inspect_text_format_class(self, tmp_path: Path) -> None:
        from axm_ast.tools.inspect import InspectTool

        pkg = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": 'class Foo:\n    """A foo."""\n    def bar(self): pass\n',
            },
        )
        result = InspectTool().execute(path=str(pkg), symbol="Foo", format="text")
        assert result.success is True

    def test_inspect_variable(self, tmp_path: Path) -> None:
        from axm_ast.tools.inspect import InspectTool

        pkg = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": "MY_CONST = 42\n",
            },
        )
        result = InspectTool().execute(path=str(pkg), symbol="MY_CONST")
        assert result.success is True

    def test_inspect_with_source(self, tmp_path: Path) -> None:
        from axm_ast.tools.inspect import InspectTool

        pkg = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": "def hello():\n    return 'hi'\n",
            },
        )
        result = InspectTool().execute(path=str(pkg), symbol="hello", source=True)
        assert result.success is True


class TestDottedPathResolution:
    """Tests for dotted path resolution (module.symbol and Class.method)."""

    def test_dotted_module_function(
        self, tool__from_inspect_tool: InspectTool, rich_pkg__from_inspect: Path
    ) -> None:
        """core.greet → function greet in core module."""
        result = tool__from_inspect_tool.execute(
            path=str(rich_pkg__from_inspect), symbol="core.greet"
        )
        assert result.success is True
        assert result.data["symbol"]["name"] == "greet"

    def test_dotted_module_class(
        self, tool__from_inspect_tool: InspectTool, rich_pkg__from_inspect: Path
    ) -> None:
        """core.MyClass → class in core module."""
        result = tool__from_inspect_tool.execute(
            path=str(rich_pkg__from_inspect), symbol="core.MyClass"
        )
        assert result.success is True
        assert result.data["symbol"]["name"] == "MyClass"

    def test_dotted_class_method(
        self, tool__from_inspect_tool: InspectTool, rich_pkg__from_inspect: Path
    ) -> None:
        """MyClass.my_method → method in class."""
        result = tool__from_inspect_tool.execute(
            path=str(rich_pkg__from_inspect), symbol="MyClass.my_method"
        )
        assert result.success is True
        assert result.data["symbol"]["name"] == "my_method"

    def test_dotted_nested_module(
        self, tool__from_inspect_tool: InspectTool, rich_pkg__from_inspect: Path
    ) -> None:
        """sub.helpers.helper_func → function in nested module."""
        result = tool__from_inspect_tool.execute(
            path=str(rich_pkg__from_inspect), symbol="sub.helpers.helper_func"
        )
        assert result.success is True
        assert result.data["symbol"]["name"] == "helper_func"

    def test_dotted_not_found(
        self, tool__from_inspect_tool: InspectTool, rich_pkg__from_inspect: Path
    ) -> None:
        """Module found but symbol missing → error."""
        result = tool__from_inspect_tool.execute(
            path=str(rich_pkg__from_inspect), symbol="core.nonexistent"
        )
        assert result.success is False
        assert result.error is not None
        assert "nonexistent" in result.error

    def test_double_dotted_not_found(
        self, tool__from_inspect_tool: InspectTool, rich_pkg__from_inspect: Path
    ) -> None:
        """Neither module nor class match → combined error."""
        result = tool__from_inspect_tool.execute(
            path=str(rich_pkg__from_inspect), symbol="fake.module.xyz"
        )
        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error


class TestInspectEdgeCasesIntegration:
    """Edge cases for InspectTool (real I/O)."""

    def test_symbols_batch_success(
        self, tool__from_inspect_tool: InspectTool, rich_pkg__from_inspect: Path
    ) -> None:
        result = tool__from_inspect_tool.execute(
            path=str(rich_pkg__from_inspect), symbols=["greet", "MyClass"]
        )
        assert result.success is True
        assert "symbols" in result.data
        symbols = result.data["symbols"]
        assert len(symbols) == 2
        assert symbols[0]["name"] == "greet"
        assert symbols[1]["name"] == "MyClass"

    def test_symbols_batch_partial_missing(
        self, tool__from_inspect_tool: InspectTool, rich_pkg__from_inspect: Path
    ) -> None:
        result = tool__from_inspect_tool.execute(
            path=str(rich_pkg__from_inspect), symbols=["greet", "missing_xyz", "core"]
        )
        assert result.success is True
        symbols = result.data["symbols"]
        assert len(symbols) == 3

        # 0: greet (success)
        assert symbols[0]["name"] == "greet"
        assert "signature" in symbols[0]

        # 1: missing_xyz (error)
        assert symbols[1]["name"] == "missing_xyz"
        assert "error" in symbols[1]
        assert "not found" in symbols[1]["error"]

        # 2: core (module fallback success)
        assert symbols[2]["name"] == "core"
        assert symbols[2]["kind"] == "module"

    def test_symbol_not_found(
        self, tool__from_inspect_tool: InspectTool, rich_pkg__from_inspect: Path
    ) -> None:
        result = tool__from_inspect_tool.execute(
            path=str(rich_pkg__from_inspect), symbol="totally_missing_xyz"
        )
        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error

    def test_empty_package(
        self, tool__from_inspect_tool: InspectTool, tmp_path: Path
    ) -> None:
        pkg = tmp_path / "empty"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        result = tool__from_inspect_tool.execute(path=str(pkg), symbol="anything")
        assert result.success is False


class TestInspectModuleFallback:
    """Tests for module fallback when symbol not found (AXM-430)."""

    def test_inspect_module_by_name(
        self, tool__from_inspect_tool: InspectTool, rich_pkg__from_inspect: Path
    ) -> None:
        """AC1: ast_inspect(symbol='core') returns module metadata."""
        result = tool__from_inspect_tool.execute(
            path=str(rich_pkg__from_inspect), symbol="core"
        )
        assert result.success is True
        sym = result.data["symbol"]
        assert sym["kind"] == "module"
        assert "functions" in sym
        assert "classes" in sym
        assert "symbol_count" in sym

    def test_inspect_module_has_file(
        self, tool__from_inspect_tool: InspectTool, rich_pkg__from_inspect: Path
    ) -> None:
        """AC2: Module metadata includes a valid relative file path."""
        result = tool__from_inspect_tool.execute(
            path=str(rich_pkg__from_inspect), symbol="core"
        )
        assert result.success is True
        sym = result.data["symbol"]
        assert sym["file"]
        assert "core.py" in sym["file"]

    def test_inspect_module_has_docstring(
        self, tool__from_inspect_tool: InspectTool, rich_pkg__from_inspect: Path
    ) -> None:
        """AC2: Module metadata includes docstring when present."""
        result = tool__from_inspect_tool.execute(
            path=str(rich_pkg__from_inspect), symbol="core"
        )
        assert result.success is True
        sym = result.data["symbol"]
        assert sym["docstring"] == "Core module."

    def test_inspect_symbol_still_preferred(
        self, tool__from_inspect_tool: InspectTool, rich_pkg__from_inspect: Path
    ) -> None:
        """AC3: Symbol match takes priority over module fallback."""
        result = tool__from_inspect_tool.execute(
            path=str(rich_pkg__from_inspect), symbol="greet"
        )
        assert result.success is True
        sym = result.data["symbol"]
        assert sym["name"] == "greet"
        assert sym.get("kind") != "module"
        assert "signature" in sym

    def test_no_match_still_errors(
        self, tool__from_inspect_tool: InspectTool, rich_pkg__from_inspect: Path
    ) -> None:
        """Edge: No symbol and no module → error."""
        result = tool__from_inspect_tool.execute(
            path=str(rich_pkg__from_inspect), symbol="zzz_nonexistent"
        )
        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error

    def test_inspect_nested_module(
        self, tool__from_inspect_tool: InspectTool, rich_pkg__from_inspect: Path
    ) -> None:
        """Module fallback works for nested modules via dotted name."""
        result = tool__from_inspect_tool.execute(
            path=str(rich_pkg__from_inspect), symbol="sub.helpers"
        )
        assert result.success is True
        sym = result.data["symbol"]
        assert sym["kind"] == "module"
        assert "helper_func" in sym["functions"]


class TestInspectToolIntegration:
    """Tests for ast_inspect tool."""

    def test_inspect_function(self, sample_project: Path) -> None:
        from axm_ast.tools.inspect import InspectTool

        tool__from_inspect_tool = InspectTool()
        result = tool__from_inspect_tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="greet"
        )
        _assert_tool_result(result)
        assert result.success is True
        assert "symbol" in result.data

    def test_inspect_class(self, sample_project: Path) -> None:
        from axm_ast.tools.inspect import InspectTool

        tool__from_inspect_tool = InspectTool()
        result = tool__from_inspect_tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="Helper"
        )
        assert result.success is True
        assert result.data["symbol"]["name"] == "Helper"

    def test_missing_symbol_param(self, sample_project: Path) -> None:
        from axm_ast.tools.inspect import InspectTool

        tool__from_inspect_tool = InspectTool()
        result = tool__from_inspect_tool.execute(
            path=str(sample_project / "src" / "demo")
        )
        assert result.success is False

    def test_inspect_dotted_method(self, sample_project: Path) -> None:
        from axm_ast.tools.inspect import InspectTool

        tool__from_inspect_tool = InspectTool()
        result = tool__from_inspect_tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="Helper.run"
        )
        assert result.success is True
        assert result.data["symbol"]["name"] == "run"

    def test_inspect_dotted_property(self, sample_project: Path) -> None:
        from axm_ast.tools.inspect import InspectTool

        tool__from_inspect_tool = InspectTool()
        result = tool__from_inspect_tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="Helper.label"
        )
        assert result.success is True
        assert result.data["symbol"]["name"] == "label"

    def test_inspect_dotted_classmethod(self, sample_project: Path) -> None:
        from axm_ast.tools.inspect import InspectTool

        tool__from_inspect_tool = InspectTool()
        result = tool__from_inspect_tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="Helper.from_name"
        )
        assert result.success is True
        assert result.data["symbol"]["name"] == "from_name"

    def test_inspect_dotted_not_found(self, sample_project: Path) -> None:
        from axm_ast.tools.inspect import InspectTool

        tool__from_inspect_tool = InspectTool()
        result = tool__from_inspect_tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="Helper.nonexistent"
        )
        assert result.success is False
        assert result.error is not None
        assert "nonexistent" in result.error
        assert "Helper" in result.error

    def test_inspect_class_not_found_dotted(self, sample_project: Path) -> None:
        from axm_ast.tools.inspect import InspectTool

        tool__from_inspect_tool = InspectTool()
        result = tool__from_inspect_tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="Missing.method"
        )
        assert result.success is False
        assert result.error is not None
        assert "Missing" in result.error

    def test_inspect_toplevel_unchanged(self, sample_project: Path) -> None:
        """Regression: top-level symbols still work (AC5)."""
        from axm_ast.tools.inspect import InspectTool

        tool__from_inspect_tool = InspectTool()
        result = tool__from_inspect_tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="greet"
        )
        assert result.success is True
        assert result.data["symbol"]["name"] == "greet"

    # --- Module.function resolution (AXM-54) ---

    def test_inspect_module_function(self, sample_project: Path) -> None:
        """AC1: core.greet resolves to greet in core module."""
        from axm_ast.tools.inspect import InspectTool

        tool__from_inspect_tool = InspectTool()
        result = tool__from_inspect_tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="core.greet"
        )
        assert result.success is True
        assert result.data["symbol"]["name"] == "greet"

    def test_inspect_module_class(self, sample_project: Path) -> None:
        """AC2: core.Helper resolves to Helper class in core module."""
        from axm_ast.tools.inspect import InspectTool

        tool__from_inspect_tool = InspectTool()
        result = tool__from_inspect_tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="core.Helper"
        )
        assert result.success is True
        assert result.data["symbol"]["name"] == "Helper"

    def test_inspect_module_symbol_not_found(self, sample_project: Path) -> None:
        """Module found but symbol does not exist in it."""
        from axm_ast.tools.inspect import InspectTool

        tool__from_inspect_tool = InspectTool()
        result = tool__from_inspect_tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="core.nonexistent"
        )
        assert result.success is False
        assert result.error is not None
        assert "core" in result.error
        assert "nonexistent" in result.error

    def test_inspect_unknown_module_falls_back_to_class(
        self, sample_project: Path
    ) -> None:
        """AC4: unknown prefix falls back to ClassName.method."""
        from axm_ast.tools.inspect import InspectTool

        tool__from_inspect_tool = InspectTool()
        # Helper.run should still work via class method fallback
        result = tool__from_inspect_tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="Helper.run"
        )
        assert result.success is True
        assert result.data["symbol"]["name"] == "run"

    def test_inspect_no_match_at_all(self, sample_project: Path) -> None:
        """No module and no class matches → combined error."""
        from axm_ast.tools.inspect import InspectTool

        tool__from_inspect_tool = InspectTool()
        result = tool__from_inspect_tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="nonexistent.xyz"
        )
        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error

    # --- Line info and source (AXM-396) ---

    def test_inspect_includes_line_info(self, sample_project: Path) -> None:
        """AC1: inspect returns file, start_line, end_line for a function."""
        from axm_ast.tools.inspect import InspectTool

        tool__from_inspect_tool = InspectTool()
        result = tool__from_inspect_tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="greet"
        )
        assert result.success is True
        sym = result.data["symbol"]
        assert "file" in sym
        assert "start_line" in sym
        assert "end_line" in sym
        assert sym["start_line"] > 0
        assert sym["end_line"] >= sym["start_line"]
        assert "core.py" in sym["file"]

    def test_inspect_class_line_info(self, sample_project: Path) -> None:
        """AC1+AC4: class line info spans full class body."""
        from axm_ast.tools.inspect import InspectTool

        tool__from_inspect_tool = InspectTool()
        result = tool__from_inspect_tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="Helper"
        )
        assert result.success is True
        sym = result.data["symbol"]
        assert sym["start_line"] > 0
        assert sym["end_line"] > sym["start_line"]  # multi-line class

    def test_inspect_method_line_info(self, sample_project: Path) -> None:
        """AC4: method line info is for the method only, not the class."""
        from axm_ast.tools.inspect import InspectTool

        tool__from_inspect_tool = InspectTool()
        cls_result = tool__from_inspect_tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="Helper"
        )
        method_result = tool__from_inspect_tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="Helper.run"
        )
        assert cls_result.success is True
        assert method_result.success is True
        cls_sym = cls_result.data["symbol"]
        method_sym = method_result.data["symbol"]
        # Method lines are within class lines
        assert method_sym["start_line"] >= cls_sym["start_line"]
        assert method_sym["end_line"] <= cls_sym["end_line"]

    def test_inspect_source_true(self, sample_project: Path) -> None:
        """AC2: source=True includes source code."""
        from axm_ast.tools.inspect import InspectTool

        tool__from_inspect_tool = InspectTool()
        result = tool__from_inspect_tool.execute(
            path=str(sample_project / "src" / "demo"),
            symbol="greet",
            source=True,
        )
        assert result.success is True
        sym = result.data["symbol"]
        assert "source" in sym
        assert "def greet" in sym["source"]
        assert "Hello" in sym["source"]

    def test_inspect_source_false_default(self, sample_project: Path) -> None:
        """AC3: source is absent by default."""
        from axm_ast.tools.inspect import InspectTool

        tool__from_inspect_tool = InspectTool()
        result = tool__from_inspect_tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="greet"
        )
        assert result.success is True
        assert "source" not in result.data["symbol"]
