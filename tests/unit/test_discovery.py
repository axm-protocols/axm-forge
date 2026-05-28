"""Unit tests for ``axm_mcp.discovery``.

Merged from four aspect-split mirror sources:
- test_disable_tools.py    (AXM_DISABLE_TOOLS filtering: _is_disabled, discover_tools)
- test_mcp_bib.py          (bib tool discovery + registration)
- test_mcp_tools.py        (formal tool discovery)
- test_typed_schema.py     (_register_one typed-schema preservation)

Helper namespacing: the two divergent ``_make_ep`` helpers were renamed
``_make_bib_ep`` (test_mcp_bib origin) and ``_make_formal_ep``
(test_mcp_tools origin) to avoid silent shadowing.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Literal
from unittest.mock import MagicMock, patch

import pydantic
import pytest
from axm.tools.base import ToolResult
from tests.unit._helpers import _DISCOVER

from axm_mcp.discovery import (
    _is_disabled,
    _register_list_tools,
    _register_one,
    discover_tools,
    register_tools,
)

# ─────────────────────────────── disable patterns ────────────────────────────


class TestIsDisabled:
    """Unit tests for the _is_disabled helper."""

    def test_exact_match(self) -> None:
        assert _is_disabled("ast_dead_code", ["ast_dead_code"]) is True

    def test_glob_match(self) -> None:
        assert _is_disabled("bib_search", ["bib_*"]) is True

    def test_no_match(self) -> None:
        assert _is_disabled("git_commit", ["bib_*"]) is False

    def test_empty_patterns(self) -> None:
        assert _is_disabled("anything", []) is False

    def test_multiple_patterns_first_matches(self) -> None:
        assert _is_disabled("bib_search", ["bib_*", "ast_*"]) is True

    def test_multiple_patterns_second_matches(self) -> None:
        assert _is_disabled("ast_inspect", ["bib_*", "ast_*"]) is True

    def test_multiple_patterns_none_matches(self) -> None:
        assert _is_disabled("git_commit", ["bib_*", "ast_dead_code"]) is False

    def test_wildcard_matches_all(self) -> None:
        assert _is_disabled("anything", ["*"]) is True


class _FakeEntryPoint:
    """Minimal entry point stub for testing discovery filtering."""

    def __init__(self, name: str) -> None:
        self.name = name

    def load(self) -> Any:
        """Return a plain callable (dispatcher pattern)."""

        def _dummy(**kwargs: Any) -> dict[str, Any]:
            return {"tool": self.name}

        _dummy.__doc__ = f"Fake tool {self.name}."
        return _dummy


_FAKE_EPS = [
    _FakeEntryPoint("ast_context"),
    _FakeEntryPoint("ast_dead_code"),
    _FakeEntryPoint("ast_diff"),
    _FakeEntryPoint("bib_search"),
    _FakeEntryPoint("bib_resolve"),
    _FakeEntryPoint("git_commit"),
]


def _mock_entry_points(group: str) -> list[_FakeEntryPoint]:
    """Return fake entry points for axm.tools group."""
    if group == "axm.tools":
        return list(_FAKE_EPS)
    return []


class TestDiscoverToolsFiltering:
    """Integration tests for discover_tools with AXM_DISABLE_TOOLS."""

    @patch("axm_mcp.discovery.importlib.metadata.entry_points", _mock_entry_points)
    def test_no_env_var_discovers_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without AXM_DISABLE_TOOLS, all tools are discovered."""
        monkeypatch.delenv("AXM_DISABLE_TOOLS", raising=False)
        tools = discover_tools()
        assert len(tools) == 6
        assert "ast_context" in tools
        assert "bib_search" in tools

    @patch("axm_mcp.discovery.importlib.metadata.entry_points", _mock_entry_points)
    def test_exact_name_excludes_tool(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Exact name excludes a single tool."""
        monkeypatch.setenv("AXM_DISABLE_TOOLS", "ast_dead_code")
        tools = discover_tools()
        assert "ast_dead_code" not in tools
        assert "ast_context" in tools
        assert len(tools) == 5

    @patch("axm_mcp.discovery.importlib.metadata.entry_points", _mock_entry_points)
    def test_glob_pattern_excludes_group(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Glob pattern excludes an entire tool group."""
        monkeypatch.setenv("AXM_DISABLE_TOOLS", "bib_*")
        tools = discover_tools()
        assert "bib_search" not in tools
        assert "bib_resolve" not in tools
        assert "ast_context" in tools
        assert len(tools) == 4

    @patch("axm_mcp.discovery.importlib.metadata.entry_points", _mock_entry_points)
    def test_multiple_patterns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Multiple patterns (glob + exact) combine correctly."""
        monkeypatch.setenv("AXM_DISABLE_TOOLS", "bib_*,ast_dead_code")
        tools = discover_tools()
        assert "bib_search" not in tools
        assert "bib_resolve" not in tools
        assert "ast_dead_code" not in tools
        assert "ast_context" in tools
        assert "git_commit" in tools
        assert len(tools) == 3

    @patch("axm_mcp.discovery.importlib.metadata.entry_points", _mock_entry_points)
    def test_empty_string_discovers_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty string means no filtering."""
        monkeypatch.setenv("AXM_DISABLE_TOOLS", "")
        tools = discover_tools()
        assert len(tools) == 6

    @patch("axm_mcp.discovery.importlib.metadata.entry_points", _mock_entry_points)
    def test_whitespace_handling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Whitespace around patterns is stripped."""
        monkeypatch.setenv("AXM_DISABLE_TOOLS", " bib_* , ast_dead_code ")
        tools = discover_tools()
        assert "bib_search" not in tools
        assert "ast_dead_code" not in tools
        assert len(tools) == 3

    @patch("axm_mcp.discovery.importlib.metadata.entry_points", _mock_entry_points)
    def test_wildcard_disables_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Wildcard '*' disables all tools."""
        monkeypatch.setenv("AXM_DISABLE_TOOLS", "*")
        tools = discover_tools()
        assert len(tools) == 0

    @patch("axm_mcp.discovery.importlib.metadata.entry_points", _mock_entry_points)
    def test_consecutive_commas_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Consecutive commas produce empty strings that are ignored."""
        monkeypatch.setenv("AXM_DISABLE_TOOLS", "bib_*,,ast_dead_code")
        tools = discover_tools()
        assert "bib_search" not in tools
        assert "ast_dead_code" not in tools
        assert len(tools) == 3


# ─────────────────────────────── bib discovery ───────────────────────────────


def _make_bib_ep(name: str, tool_instance: Any | None = None) -> MagicMock:
    """Build a fake entry-point that loads *tool_instance* (or a default)."""
    if tool_instance is None:
        tool_instance = MagicMock()
        tool_instance.name = name
    ep = MagicMock()
    ep.name = name
    # Use spec=type so isinstance(obj, type) returns True in discover_tools
    mock_cls = MagicMock(spec=type, return_value=tool_instance)
    ep.load.return_value = mock_cls
    return ep


class TestToolDiscovery:
    """Auto-discovery of AXMTool entry points."""

    @patch(_DISCOVER)
    def test_discovers_entry_points(self, mock_eps: MagicMock) -> None:
        """Discovers and instantiates tools from axm.tools group."""
        mock_tool_cls = MagicMock(spec=type)
        mock_tool_instance = MagicMock()
        mock_tool_instance.name = "fake_tool"
        mock_tool_cls.return_value = mock_tool_instance

        ep = MagicMock()
        ep.name = "fake_tool"
        ep.load.return_value = mock_tool_cls
        mock_eps.return_value = [ep]

        tools = discover_tools()
        assert "fake_tool" in tools
        assert tools["fake_tool"] is mock_tool_instance

    @patch(_DISCOVER)
    def test_skips_broken_entry_point(self, mock_eps: MagicMock) -> None:
        """Broken entry point is skipped, not fatal."""
        ep = MagicMock()
        ep.name = "broken"
        ep.load.side_effect = ImportError("missing dep")
        mock_eps.return_value = [ep]

        tools = discover_tools()
        assert len(tools) == 0

    @patch(_DISCOVER)
    def test_multiple_packages(self, mock_eps: MagicMock) -> None:
        """Tools from multiple packages co-exist."""
        tool_a = MagicMock()
        tool_a.name = "tool_a"
        ep_a = MagicMock()
        ep_a.name = "tool_a"
        ep_a.load.return_value = MagicMock(spec=type, return_value=tool_a)

        tool_b = MagicMock()
        tool_b.name = "tool_b"
        ep_b = MagicMock()
        ep_b.name = "tool_b"
        ep_b.load.return_value = MagicMock(spec=type, return_value=tool_b)

        mock_eps.return_value = [ep_a, ep_b]

        tools = discover_tools()
        assert "tool_a" in tools
        assert "tool_b" in tools

    @patch(_DISCOVER)
    def test_empty_no_packages(self, mock_eps: MagicMock) -> None:
        """No packages installed → empty dict, no crash."""
        mock_eps.return_value = []
        tools = discover_tools()
        assert tools == {}


class TestMCPRegistration:
    """Discovered tools get registered as MCP tools."""

    @patch(_DISCOVER)
    def test_register_creates_mcp_tool(self, mock_eps: MagicMock) -> None:
        """register_tools adds a tool callable to the MCP server."""
        from axm_mcp.mcp_app import mcp

        mock_tool = MagicMock()
        mock_tool.name = "test_register"
        mock_tool.execute.return_value = ToolResult(success=True, data={"x": 1})

        ep = MagicMock()
        ep.name = "test_register"
        ep.load.return_value = MagicMock(spec=type, return_value=mock_tool)
        mock_eps.return_value = [ep]

        tools = discover_tools()
        register_tools(mcp, tools)

        # The tool should be listed in mcp's tools
        tool_names = [t.name for t in mcp._tool_manager._tools.values()]
        assert "test_register" in tool_names


class TestBibSearchMCP:
    """MCP bib_search tool tests — all discovered via mocked entry points."""

    @patch(_DISCOVER)
    def test_bib_search_tool_exists(self, mock_eps: MagicMock) -> None:
        """bib_search is discoverable from axm.tools."""
        mock_eps.return_value = [_make_bib_ep("bib_search")]
        tools = discover_tools()
        assert "bib_search" in tools

    @patch(_DISCOVER)
    def test_bib_search_happy_path(self, mock_eps: MagicMock) -> None:
        """Returns papers list."""
        tool = MagicMock()
        tool.name = "bib_search"
        tool.execute.return_value = ToolResult(
            success=True,
            data={"papers": [{"title": "Test", "doi": "10.1/x"}], "count": 1},
        )
        mock_eps.return_value = [_make_bib_ep("bib_search", tool)]

        tools = discover_tools()
        result = tools["bib_search"].execute(query="AI")
        assert result.success
        assert result.data["count"] == 1

    @patch(_DISCOVER)
    def test_bib_search_empty_query(self, mock_eps: MagicMock) -> None:
        """Empty query returns error."""
        tool = MagicMock()
        tool.name = "bib_search"
        tool.execute.return_value = ToolResult(success=False, error="Query is required")
        mock_eps.return_value = [_make_bib_ep("bib_search", tool)]

        tools = discover_tools()
        result = tools["bib_search"].execute(query="")
        assert not result.success

    @patch(_DISCOVER)
    def test_bib_search_api_failure(self, mock_eps: MagicMock) -> None:
        """Network error → success=False."""
        tool = MagicMock()
        tool.name = "bib_search"
        tool.execute.return_value = ToolResult(
            success=False, error="Connection refused"
        )
        mock_eps.return_value = [_make_bib_ep("bib_search", tool)]

        tools = discover_tools()
        result = tools["bib_search"].execute(query="test")
        assert not result.success
        assert "Connection" in (result.error or "")

    @patch(_DISCOVER)
    def test_bib_search_limit_param(self, mock_eps: MagicMock) -> None:
        """Limit is forwarded correctly."""
        tool = MagicMock()
        tool.name = "bib_search"
        tool.execute.return_value = ToolResult(
            success=True, data={"papers": [], "count": 0}
        )
        mock_eps.return_value = [_make_bib_ep("bib_search", tool)]

        tools = discover_tools()
        tools["bib_search"].execute(query="test", limit=3)
        tool.execute.assert_called_once_with(query="test", limit=3)


class TestBibPdfMCP:
    """MCP bib_pdf tool tests."""

    @patch(_DISCOVER)
    def test_bib_pdf_tool_exists(self, mock_eps: MagicMock) -> None:
        """bib_pdf is discoverable."""
        mock_eps.return_value = [_make_bib_ep("bib_pdf")]
        tools = discover_tools()
        assert "bib_pdf" in tools

    @patch(_DISCOVER)
    def test_bib_pdf_happy_path(self, mock_eps: MagicMock) -> None:
        """Returns path + size."""
        tool = MagicMock()
        tool.name = "bib_pdf"
        tool.execute.return_value = ToolResult(
            success=True,
            data={
                "path": "/tmp/paper.pdf",
                "size_bytes": 42000,
                "is_open_access": True,
            },
        )
        mock_eps.return_value = [_make_bib_ep("bib_pdf", tool)]

        tools = discover_tools()
        result = tools["bib_pdf"].execute(doi="10.1/x")
        assert result.success
        assert result.data["is_open_access"] is True

    @patch(_DISCOVER)
    def test_bib_pdf_not_open_access(self, mock_eps: MagicMock) -> None:
        """Non-OA returns is_open_access=False."""
        tool = MagicMock()
        tool.name = "bib_pdf"
        tool.execute.return_value = ToolResult(
            success=True,
            data={
                "path": None,
                "is_open_access": False,
                "message": "Not open access",
            },
        )
        mock_eps.return_value = [_make_bib_ep("bib_pdf", tool)]

        tools = discover_tools()
        result = tools["bib_pdf"].execute(doi="10.1/closed")
        assert result.success
        assert result.data["is_open_access"] is False

    @patch(_DISCOVER)
    def test_bib_pdf_empty_doi(self, mock_eps: MagicMock) -> None:
        """Empty DOI → error."""
        tool = MagicMock()
        tool.name = "bib_pdf"
        tool.execute.return_value = ToolResult(success=False, error="DOI is required")
        mock_eps.return_value = [_make_bib_ep("bib_pdf", tool)]

        tools = discover_tools()
        result = tools["bib_pdf"].execute(doi="")
        assert not result.success


# ─────────────────────────────── tool discovery ──────────────────────────────


def _make_formal_ep(name: str, tool_instance: Any | None = None) -> MagicMock:
    """Build a fake entry-point that loads *tool_instance* (or a default)."""
    if tool_instance is None:
        tool_instance = MagicMock()
        tool_instance.name = name
    ep = MagicMock()
    ep.name = name
    ep.load.return_value = MagicMock(spec=type, return_value=tool_instance)
    return ep


class TestFormalToolsDiscovered:
    """Formal tools are discovered from axm-formal entry points."""

    @patch(_DISCOVER)
    def test_formal_esbmc_discovered(self, mock_eps: MagicMock) -> None:
        """formal_esbmc is discoverable from axm.tools."""
        mock_eps.return_value = [_make_formal_ep("formal_esbmc")]
        tools = discover_tools()
        assert "formal_esbmc" in tools

    @patch(_DISCOVER)
    def test_formal_dafny_discovered(self, mock_eps: MagicMock) -> None:
        """formal_dafny is discoverable from axm.tools."""
        mock_eps.return_value = [_make_formal_ep("formal_dafny")]
        tools = discover_tools()
        assert "formal_dafny" in tools

    @patch(_DISCOVER)
    def test_formal_kind2_discovered(self, mock_eps: MagicMock) -> None:
        """formal_kind2 is discoverable from axm.tools."""
        mock_eps.return_value = [_make_formal_ep("formal_kind2")]
        tools = discover_tools()
        assert "formal_kind2" in tools


class TestVerifyViaMCP:
    """Verify tool via auto-discovery (mocked)."""

    @patch(_DISCOVER)
    def test_verify_happy_path(self, mock_eps: MagicMock) -> None:
        """formal_esbmc returns success."""
        tool = MagicMock()
        tool.name = "formal_esbmc"
        tool.execute.return_value = ToolResult(success=True, data={"verified": True})
        mock_eps.return_value = [_make_formal_ep("formal_esbmc", tool)]

        tools = discover_tools()
        result = tools["formal_esbmc"].execute(source_file="/tmp/test.c")
        assert result.success

    @patch(_DISCOVER)
    def test_verify_failure(self, mock_eps: MagicMock) -> None:
        """formal_esbmc returns verification failure."""
        tool = MagicMock()
        tool.name = "formal_esbmc"
        tool.execute.return_value = ToolResult(
            success=False, error="Verification failed: buffer overflow"
        )
        mock_eps.return_value = [_make_formal_ep("formal_esbmc", tool)]

        tools = discover_tools()
        result = tools["formal_esbmc"].execute(source_file="/tmp/test.c")
        assert not result.success
        assert "buffer overflow" in (result.error or "")


# ───────────────────────── typed schema registration ─────────────────────────


class FakeMCP:
    """Minimal FastMCP stand-in that captures registered tools."""

    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self, *, name: str) -> Any:
        def decorator(fn: Any) -> Any:
            self.tools[name] = fn
            return fn

        return decorator


class ReplaceOp(pydantic.BaseModel):
    """Replace operation."""

    op: Literal["replace"] = "replace"
    file: str
    edits: list[dict[str, str]]


class CreateOp(pydantic.BaseModel):
    """Create operation."""

    op: Literal["create"] = "create"
    file: str
    content: str


class DeleteOp(pydantic.BaseModel):
    """Delete operation."""

    op: Literal["delete"] = "delete"
    file: str


class TestComplexParamSchemaPreserved:
    """Complex union params must retain discriminated type info."""

    def test_complex_param_schema_preserved(self) -> None:
        """Register tool with list[ReplaceOp | CreateOp] param.

        The wrapper signature must preserve the annotation so FastMCP
        can generate a JSON-Schema with discriminated union types.
        """

        class ComplexTool:
            def execute(
                self,
                *,
                path: str,
                operations: list[ReplaceOp | CreateOp | DeleteOp],
            ) -> Any:
                """Apply batch operations.

                Args:
                    path: Target project path.
                    operations: List of edit operations.

                Returns:
                    ToolResult with results.
                """

                class _R:
                    success = True
                    data: dict[str, Any] = {"applied": len(operations)}
                    error = None

                return _R()

        fake_mcp = FakeMCP()
        _register_one(fake_mcp, "complex_tool", ComplexTool())

        wrapper = fake_mcp.tools["complex_tool"]
        sig = inspect.signature(wrapper)

        # The 'operations' parameter must exist
        assert "operations" in sig.parameters
        ann = sig.parameters["operations"].annotation

        # The annotation must NOT be reduced to a plain type —
        # it should preserve the union/list structure
        assert ann is not inspect.Parameter.empty, (
            "Complex param annotation was stripped"
        )

        # Verify the annotation string contains the union types
        ann_str = str(ann)
        assert "ReplaceOp" in ann_str, f"ReplaceOp lost from annotation: {ann_str}"
        assert "CreateOp" in ann_str, f"CreateOp lost from annotation: {ann_str}"
        assert "DeleteOp" in ann_str, f"DeleteOp lost from annotation: {ann_str}"


class TestSimpleParamUnchanged:
    """Simple str/int params must keep their existing behavior."""

    def test_simple_param_unchanged(self) -> None:
        """Register tool with str, int params — schema identical."""

        class SimpleTool:
            def execute(
                self,
                *,
                path: str,
                limit: int = 10,
                verbose: bool = False,
            ) -> Any:
                """Do something simple.

                Args:
                    path: Target path.
                    limit: Max results.
                    verbose: Enable verbose output.

                Returns:
                    ToolResult with data.
                """

                class _R:
                    success = True
                    data = {"path": path, "limit": limit}
                    error = None

                return _R()

        fake_mcp = FakeMCP()
        _register_one(fake_mcp, "simple_tool", SimpleTool())

        wrapper = fake_mcp.tools["simple_tool"]
        sig = inspect.signature(wrapper)
        params = sig.parameters

        assert params["path"].annotation is str
        assert params["limit"].annotation is int
        assert params["limit"].default == 10
        assert params["verbose"].annotation is bool
        assert params["verbose"].default is False


class TestAllExistingToolsRegister:
    """All discovered tools must register without error."""

    def test_all_existing_tools_register(self) -> None:
        """discover_tools() + register_tools() succeeds for every tool."""
        tools = discover_tools()
        assert len(tools) > 0, "No tools discovered"

        fake_mcp = FakeMCP()
        # Must not raise
        register_tools(fake_mcp, tools)

        # Every discovered tool should be registered
        for name in tools:
            assert name in fake_mcp.tools, (
                f"Tool '{name}' discovered but not registered"
            )


class TestBatchEditSchemaViaMCP:
    """batch_edit schema must expose typed operation fields via _register_one."""

    def test_batch_edit_schema_via_mcp(self) -> None:
        """Register a batch_edit-like tool and verify typed schema fields.

        Uses a self-contained fake tool with the same signature shape as
        the real batch_edit (path + operations with union types), so the
        test doesn't depend on axm-edit being installed.
        """

        class FakeBatchEditTool:
            def execute(
                self,
                *,
                path: str,
                operations: list[ReplaceOp | CreateOp | DeleteOp],
            ) -> Any:
                """Apply batch file operations.

                Args:
                    path: Project root directory.
                    operations: List of edit operations.

                Returns:
                    ToolResult with results.
                """

                class _R:
                    success = True
                    data: dict[str, Any] = {"applied": len(operations)}
                    error = None

                return _R()

        fake_mcp = FakeMCP()
        _register_one(fake_mcp, "batch_edit", FakeBatchEditTool())

        wrapper = fake_mcp.tools["batch_edit"]
        sig = inspect.signature(wrapper)

        # batch_edit must expose 'path' and 'operations' params
        param_names = list(sig.parameters.keys())
        assert "path" in param_names, (
            f"'path' missing from batch_edit params: {param_names}"
        )
        assert "operations" in param_names, (
            f"'operations' missing from batch_edit params: {param_names}"
        )

        # The 'operations' annotation must preserve the typed schema
        ops_ann = sig.parameters["operations"].annotation
        assert ops_ann is not inspect.Parameter.empty, (
            "batch_edit 'operations' annotation was stripped"
        )


# ───────────────────────── wrapper registration ──────────────────────────────


@dataclass
class FakeToolResult:
    """Minimal ToolResult stand-in."""

    success: bool = True
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class FakeTool:
    """Minimal ToolLike stand-in for testing registration."""

    def __init__(
        self,
        name: str = "fake_tool",
        *,
        result: FakeToolResult | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self._name = name
        self._result = result or FakeToolResult(data={"key": "val"})
        self._raise_exc = raise_exc

    @property
    def name(self) -> str:
        return self._name

    def execute(self, **kwargs: Any) -> FakeToolResult:
        """Execute the fake tool."""
        if self._raise_exc:
            raise self._raise_exc
        return self._result


class TestRegisterOne:
    """Cover _register_one wrapper (discovery.py:91-97)."""

    def test_wrapper_returns_success(self) -> None:
        """Registered wrapper returns tool result as dict."""
        fake_mcp = FakeMCP()
        tool = FakeTool(result=FakeToolResult(success=True, data={"answer": 42}))
        _register_one(fake_mcp, "my_tool", tool)

        result = fake_mcp.tools["my_tool"]()
        assert result == {"success": True, "answer": 42}

    def test_wrapper_includes_error(self) -> None:
        """Wrapper includes error field when tool reports one."""
        fake_mcp = FakeMCP()
        tool = FakeTool(
            result=FakeToolResult(success=False, data={}, error="something broke"),
        )
        _register_one(fake_mcp, "err_tool", tool)

        result = fake_mcp.tools["err_tool"]()
        assert result["success"] is False
        assert result["error"] == "something broke"

    def test_wrapper_unwraps_nested_kwargs(self) -> None:
        """Wrapper unwraps kwargs={...} pattern from MCP."""
        fake_mcp = FakeMCP()
        tool = FakeTool(result=FakeToolResult(success=True, data={"ok": True}))
        _register_one(fake_mcp, "unwrap_tool", tool)

        result = fake_mcp.tools["unwrap_tool"](kwargs={"path": "/tmp"})
        assert result["success"] is True


class TestRegisterListTools:
    """Cover _register_list_tools inner fn (discovery.py:113-120)."""

    def test_lists_all_tools(self) -> None:
        """list_tools returns discovered + extra tools, sorted."""
        fake_mcp = FakeMCP()
        tools = {
            "beta_tool": FakeTool(name="beta_tool"),
            "alpha_tool": FakeTool(name="alpha_tool"),
        }
        extra = {"verify": "One-shot verify"}
        _register_list_tools(fake_mcp, tools, extra)

        result = fake_mcp.tools["list_tools"]()
        assert result["count"] == 3
        names = [t["name"] for t in result["tools"]]
        assert names == ["alpha_tool", "beta_tool", "verify"]
