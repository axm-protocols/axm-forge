"""Tests targeting coverage gaps — AXM-982."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from axm_ast.core.analyzer import analyze_package
from axm_ast.formatters import (
    format_module_inspect_text,
    format_symbol_text,
)

# ─── Helpers ────────────────────────────────────────────────────────────────


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    pkg = tmp_path / "mypkg"
    for name, content in files.items():
        fp = pkg / name
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return pkg


# ─── formatters: format_symbol_text ─────────────────────────────────────────


class TestFormatSymbolText:
    """Cover _format_function_text, _format_class_text, format_symbol_text."""

    def test_format_function_text(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": (
                    "def greet(name: str) -> str:\n"
                    '    """Say hello.\n\n'
                    "    Raises:\n"
                    "        ValueError: If name is empty.\n\n"
                    "    Examples:\n"
                    "        >>> greet('world')\n"
                    "        'hello world'\n"
                    '    """\n'
                    "    return f'hello {name}'\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        mod = next(m for m in pkg.modules if m.functions)
        fn = mod.functions[0]
        text = format_symbol_text(fn)
        assert "greet" in text
        assert "Say hello" in text
        assert "ValueError" in text

    def test_format_class_text(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": (
                    "class Animal(object):\n"
                    '    """A base animal."""\n'
                    "    def speak(self) -> str:\n"
                    '        """Make sound."""\n'
                    "        return '...'\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        mod = next(m for m in pkg.modules if m.classes)
        cls = mod.classes[0]
        text = format_symbol_text(cls)
        assert "Animal" in text
        assert "object" in text
        assert "speak" in text


# ─── formatters: format_module_inspect_text ─────────────────────────────────


class TestFormatModuleInspectText:
    """Cover format_module_inspect_text and related helpers."""

    def test_format_module_inspect(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": (
                    '"""Module docstring."""\n'
                    "def public_fn() -> None:\n"
                    '    """Public."""\n'
                    "    pass\n\n"
                    "def _private_fn() -> None:\n"
                    "    pass\n\n"
                    "class Widget:\n"
                    '    """A widget."""\n'
                    "    def run(self) -> None:\n"
                    "        pass\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        mod = next(m for m in pkg.modules if m.functions or m.classes)
        text = format_module_inspect_text(mod)
        assert "mod.py" in text
        assert "Module docstring" in text
        assert "public_fn" in text
        assert "Widget" in text
        assert "run" in text


# ─── formatters: _compress_class with no docstring ──────────────────────────


class TestCompressClassNoDocstring:
    """Cover formatters line 289-290 (class without docstring → '...')."""

    def test_compress_class_no_docstring_no_methods(self, tmp_path: Path) -> None:
        from axm_ast.formatters import format_compressed

        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": "class Empty:\n    pass\n",
            },
        )
        pkg = analyze_package(pkg_path)
        text = format_compressed(pkg)
        assert "class Empty" in text


# ─── tools/impact: edge cases ───────────────────────────────────────────────


class TestImpactToolEdgeCases:
    """Cover tools/impact.py uncovered paths."""

    def test_bad_path(self) -> None:
        from axm_ast.tools.impact import ImpactTool

        result = ImpactTool().execute(path="/nonexistent/xyz", symbol="foo")
        assert result.success is False

    def test_exception(self, tmp_path: Path, mocker: MagicMock) -> None:
        from axm_ast.tools.impact import ImpactTool

        pkg = _make_pkg(tmp_path, {"__init__.py": "", "mod.py": "x = 1\n"})
        mocker.patch(
            "axm_ast.core.impact.analyze_impact",
            side_effect=RuntimeError("impact boom"),
        )
        result = ImpactTool().execute(path=str(pkg), symbol="x")
        # The _analyze_single catches exception and returns error dict
        # Then _analyze_single_result converts it to ToolResult(success=False)
        assert result.success is False
        assert "impact boom" in (result.error or "")

    def test_batch_compact(self, tmp_path: Path) -> None:
        from axm_ast.tools.impact import ImpactTool

        pkg = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": (
                    "def foo() -> None:\n    pass\n\ndef bar() -> None:\n    foo()\n"
                ),
            },
        )
        result = ImpactTool().execute(
            path=str(pkg), symbols=["foo", "bar"], detail="compact"
        )
        assert result.success is True
        assert result.data == {}
        assert result.text is not None

    def test_single_compact(self, tmp_path: Path) -> None:
        from axm_ast.tools.impact import ImpactTool

        pkg = _make_pkg(
            tmp_path,
            {"__init__.py": "", "mod.py": "def foo() -> None:\n    pass\n"},
        )
        result = ImpactTool().execute(path=str(pkg), symbol="foo", detail="compact")
        assert result.success is True
        assert result.data == {}
        assert result.text is not None

    def test_symbol_not_found_error_result(self, tmp_path: Path) -> None:
        from axm_ast.tools.impact import ImpactTool

        pkg = _make_pkg(
            tmp_path,
            {"__init__.py": "", "mod.py": "x = 1\n"},
        )
        result = ImpactTool().execute(path=str(pkg), symbol="nonexistent_sym_xyz")
        assert result.success is False
        assert "not found" in (result.error or "")


# ─── tools/graph: workspace path (mocked) ──────────────────────────────────


class TestGraphToolWorkspace:
    """Cover tools/graph.py workspace branch (lines 52-72)."""

    def test_workspace_json(self, tmp_path: Path, mocker: MagicMock) -> None:
        from axm_ast.tools.graph import GraphTool

        mocker.patch(
            "axm_ast.core.workspace.detect_workspace",
            return_value={"packages": []},
        )
        mocker.patch(
            "axm_ast.core.workspace.analyze_workspace",
            return_value={"packages": []},
        )
        mocker.patch(
            "axm_ast.core.workspace.build_workspace_dep_graph",
            return_value={"pkgA": ["pkgB"]},
        )
        pkg = _make_pkg(tmp_path, {"__init__.py": ""})
        result = GraphTool().execute(path=str(pkg))
        assert result.success is True
        assert result.data["graph"] == {"pkgA": ["pkgB"]}

    def test_workspace_mermaid(self, tmp_path: Path, mocker: MagicMock) -> None:
        from axm_ast.tools.graph import GraphTool

        mocker.patch(
            "axm_ast.core.workspace.detect_workspace",
            return_value={"packages": []},
        )
        mocker.patch(
            "axm_ast.core.workspace.analyze_workspace",
            return_value={"packages": []},
        )
        mocker.patch(
            "axm_ast.core.workspace.build_workspace_dep_graph",
            return_value={"pkgA": ["pkgB"]},
        )
        mocker.patch(
            "axm_ast.core.workspace.format_workspace_graph_mermaid",
            return_value="graph LR\n  pkgA --> pkgB",
        )
        pkg = _make_pkg(tmp_path, {"__init__.py": ""})
        result = GraphTool().execute(path=str(pkg), format="mermaid")
        assert result.success is True
        assert "mermaid" in result.data
        assert "graph" in result.data


# ─── tools/context: workspace branch ────────────────────────────────────────


class TestContextToolWorkspace:
    """Cover tools/context.py workspace branch (lines 56, 58-59)."""

    def test_workspace_context(self, tmp_path: Path, mocker: MagicMock) -> None:
        from axm_ast.tools.context import ContextTool

        mocker.patch(
            "axm_ast.core.workspace.detect_workspace",
            return_value={"packages": []},
        )
        mocker.patch(
            "axm_ast.core.workspace.build_workspace_context",
            return_value={"workspace": True, "packages": []},
        )
        pkg = _make_pkg(tmp_path, {"__init__.py": ""})
        result = ContextTool().execute(path=str(pkg))
        assert result.success is True
        assert result.data["workspace"] is True


# ─── tools/callers: workspace branch ────────────────────────────────────────


class TestCallersToolWorkspace:
    """Cover tools/callers.py workspace branch (lines 61-65)."""

    def test_workspace_callers(self, tmp_path: Path, mocker: MagicMock) -> None:
        from axm_ast.tools.callers import CallersTool

        mock_caller = MagicMock()
        mock_caller.module = "mod_a"
        mock_caller.line = 10
        mock_caller.context = "func_a"
        mock_caller.call_expression = "greet()"

        mocker.patch(
            "axm_ast.core.workspace.detect_workspace",
            return_value={"packages": []},
        )
        mocker.patch(
            "axm_ast.core.workspace.analyze_workspace",
            return_value={"packages": []},
        )
        mocker.patch(
            "axm_ast.core.callers.find_callers_workspace",
            return_value=[mock_caller],
        )
        pkg = _make_pkg(tmp_path, {"__init__.py": ""})
        result = CallersTool().execute(path=str(pkg), symbol="greet")
        assert result.success is True
        assert result.data["count"] == 1


# ─── flows tool: compact detail ─────────────────────────────────────────────


class TestFlowsToolCompact:
    """Cover tools/flows.py compact detail branch (line 61+)."""

    def test_flows_compact_detail(self, tmp_path: Path) -> None:
        from axm_ast.tools.flows import FlowsTool

        pkg = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": ("def helper():\n    pass\n\ndef main():\n    helper()\n"),
            },
        )
        result = FlowsTool().execute(path=str(pkg), entry="main", detail="compact")
        assert result.success is True
        assert "compact" in result.data

    def test_flows_entry_points(self, tmp_path: Path) -> None:
        from axm_ast.tools.flows import FlowsTool

        pkg = _make_pkg(
            tmp_path,
            {"__init__.py": "", "mod.py": "def main():\n    pass\n"},
        )
        result = FlowsTool().execute(path=str(pkg))
        assert result.success is True
        assert "entry_points" in result.data


# ─── formatters: branch coverage helpers ────────────────────────────────────


class TestFormatterBranches:
    """Cover uncovered branches in formatters."""

    def test_format_fn_text_with_docstring_detailed(self, tmp_path: Path) -> None:
        """Cover _format_fn_text branch for detailed+docstring."""
        from axm_ast.formatters import format_text

        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": (
                    '"""Module doc."""\n'
                    "def foo() -> None:\n"
                    '    """Foo doc."""\n'
                    "    pass\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        text = format_text(pkg, detail="detailed")
        assert "Foo doc" in text

    def test_format_text_detailed_with_class_docstring(self, tmp_path: Path) -> None:
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

    def test_compress_module_with_docstring(self, tmp_path: Path) -> None:
        """Cover _compress_module branch for module docstring."""
        from axm_ast.formatters import format_compressed

        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": '"""My module summary."""\n\nx = 1\n',
            },
        )
        pkg = analyze_package(pkg_path)
        text = format_compressed(pkg)
        assert "My module summary" in text


# ─── Exception handlers in tool wrappers ────────────────────────────────────


class TestToolExceptionHandlers:
    """Cover except Exception branches in tool wrappers."""

    def test_dead_code_tool_exception(self, tmp_path: Path, mocker: MagicMock) -> None:
        from axm_ast.tools.dead_code import DeadCodeTool

        pkg = _make_pkg(tmp_path, {"__init__.py": ""})
        mocker.patch(
            "axm_ast.core.dead_code.find_dead_code",
            side_effect=RuntimeError("dead boom"),
        )
        result = DeadCodeTool().execute(path=str(pkg))
        assert result.success is False
        assert "dead boom" in (result.error or "")

    def test_describe_tool_exception(self, tmp_path: Path, mocker: MagicMock) -> None:
        from axm_ast.tools.describe import DescribeTool

        pkg = _make_pkg(tmp_path, {"__init__.py": ""})
        mocker.patch(
            "axm_ast.core.cache.get_package",
            side_effect=RuntimeError("describe boom"),
        )
        result = DescribeTool().execute(path=str(pkg))
        assert result.success is False
        assert "describe boom" in (result.error or "")

    def test_docs_tool_exception(self, tmp_path: Path, mocker: MagicMock) -> None:
        from axm_ast.tools.docs import DocsTool

        pkg = _make_pkg(tmp_path, {"__init__.py": ""})
        mocker.patch(
            "axm_ast.core.docs.discover_docs",
            side_effect=RuntimeError("docs boom"),
        )
        result = DocsTool().execute(path=str(pkg))
        assert result.success is False
        assert "docs boom" in (result.error or "")

    def test_search_tool_exception(self, tmp_path: Path, mocker: MagicMock) -> None:
        from axm_ast.tools.search import SearchTool

        pkg = _make_pkg(tmp_path, {"__init__.py": ""})
        mocker.patch(
            "axm_ast.core.cache.get_package",
            side_effect=RuntimeError("search boom"),
        )
        result = SearchTool().execute(path=str(pkg), pattern="foo")
        assert result.success is False
        assert "search boom" in (result.error or "")

    def test_inspect_tool_exception(self, tmp_path: Path, mocker: MagicMock) -> None:
        from axm_ast.tools.inspect import InspectTool

        pkg = _make_pkg(tmp_path, {"__init__.py": ""})
        mocker.patch(
            "axm_ast.core.cache.get_package",
            side_effect=RuntimeError("inspect boom"),
        )
        result = InspectTool().execute(path=str(pkg), symbol="foo")
        assert result.success is False
        assert "inspect boom" in (result.error or "")

    def test_graph_tool_exception(self, tmp_path: Path, mocker: MagicMock) -> None:
        from axm_ast.tools.graph import GraphTool

        pkg = _make_pkg(tmp_path, {"__init__.py": ""})
        mocker.patch(
            "axm_ast.core.workspace.detect_workspace",
            side_effect=RuntimeError("graph boom"),
        )
        result = GraphTool().execute(path=str(pkg))
        assert result.success is False
        assert "graph boom" in (result.error or "")

    def test_impact_tool_top_exception(self, tmp_path: Path, mocker: MagicMock) -> None:
        from axm_ast.tools.impact import ImpactTool

        pkg = _make_pkg(tmp_path, {"__init__.py": ""})
        mocker.patch(
            "axm_ast.core.workspace.detect_workspace",
            side_effect=RuntimeError("top boom"),
        )
        result = ImpactTool().execute(path=str(pkg), symbol="foo")
        # _analyze_single catches it, returns error dict
        assert result.success is False

    def test_flows_tool_exception(self, tmp_path: Path, mocker: MagicMock) -> None:
        from axm_ast.tools.flows import FlowsTool

        pkg = _make_pkg(tmp_path, {"__init__.py": ""})
        mocker.patch(
            "axm_ast.core.cache.get_package",
            side_effect=RuntimeError("flows boom"),
        )
        result = FlowsTool().execute(path=str(pkg))
        assert result.success is False
        assert "flows boom" in (result.error or "")


# ─── tools/impact: workspace path ───────────────────────────────────────────


class TestImpactToolWorkspace:
    """Cover tools/impact.py workspace branch (line 168, 170)."""

    def test_workspace_impact(self, tmp_path: Path, mocker: MagicMock) -> None:
        from axm_ast.tools.impact import ImpactTool

        pkg = _make_pkg(
            tmp_path,
            {"__init__.py": "", "mod.py": "def foo():\n    pass\n"},
        )
        mocker.patch(
            "axm_ast.core.workspace.detect_workspace",
            return_value={"packages": []},
        )
        mocker.patch(
            "axm_ast.core.impact.analyze_impact_workspace",
            return_value={
                "symbol": "foo",
                "score": "LOW",
                "definition": {"module": "mod", "line": 1},
                "callers": [],
                "test_files": [],
            },
        )
        result = ImpactTool().execute(path=str(pkg), symbol="foo")
        assert result.success is True


# ─── tools/flows: resolved_module in step ───────────────────────────────────


class TestFlowsResolvedModule:
    """Cover tools/flows.py line 104 (step with resolved_module)."""

    def test_flows_step_with_resolved_module(
        self, tmp_path: Path, mocker: MagicMock
    ) -> None:
        from unittest.mock import MagicMock as MockMagic

        from axm_ast.tools.flows import FlowsTool

        step = MockMagic()
        step.name = "foo"
        step.module = "mod"
        step.line = 1
        step.depth = 0
        step.chain = ["foo"]
        step.resolved_module = "other_mod"
        step.source = None

        pkg = _make_pkg(tmp_path, {"__init__.py": ""})
        mocker.patch("axm_ast.core.cache.get_package", return_value=MagicMock())
        mocker.patch(
            "axm_ast.core.flows.trace_flow",
            return_value=([step], False),
        )
        result = FlowsTool().execute(path=str(pkg), entry="foo")
        assert result.success is True
        assert result.data["steps"][0]["resolved_module"] == "other_mod"


# ─── tools/inspect: remaining gaps ──────────────────────────────────────────


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
