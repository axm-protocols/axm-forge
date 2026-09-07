"""Unit tests for the facade ToolCatalog (no I/O, fake tools)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

import pytest
from axm.tools.base import ToolResult
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import ValidationError

from axm_mcp.facade import catalog as catalog_module
from axm_mcp.facade.catalog import ToolCatalog, UnknownToolError
from tests_axm_mcp.unit._helpers import _catalog


class _AuditTool:
    """Fake hot-path tool with domain + tags + dual-format result."""

    expose_directly = True
    domain = "audit"
    tags = frozenset({"quality", "lint"})

    @property
    def name(self) -> str:
        return "audit"

    def execute(self, *, path: str = ".", category: str | None = None) -> ToolResult:
        """Audit a project's code quality.

        Args:
            path: Project root.
            category: Optional filter.
        """
        return ToolResult(success=True, data={"score": 90}, text="audit: 90/100")


class _BibTool:
    """Fake non-hot-path tool that returns no text (data only)."""

    domain = "bib"
    tags = frozenset({"citation"})

    @property
    def name(self) -> str:
        return "bib_resolve"

    def execute(self, *, ref: str) -> ToolResult:
        """Resolve a citation reference."""
        return ToolResult(success=True, data={"doi": "10.x"})


class _TypedListTool:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, *, symbols: list[str]) -> ToolResult:
        self.calls += 1
        return ToolResult(success=True, text=str(symbols))


class _TypedScalarTool:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, *, count: int) -> ToolResult:
        self.calls += 1
        return ToolResult(success=True, text=str(count))


class _CoercibleIntTool:
    def __init__(self) -> None:
        self.received: list[int] = []

    def execute(self, *, items: int) -> ToolResult:
        self.received.append(items)
        return ToolResult(success=True, text=str(items))


def _plain(**kwargs: Any) -> dict[str, Any]:
    """Plain dispatcher tool."""
    return {"ok": 1}


@pytest.fixture
def catalog() -> ToolCatalog:
    return _catalog(audit=_AuditTool(), bib_resolve=_BibTool(), plain_tool=_plain)


class TestIntrospection:
    def test_names_sorted(self, catalog: ToolCatalog) -> None:
        assert catalog.names() == ["audit", "bib_resolve", "plain_tool"]

    def test_hot_path_only_opted_in(self, catalog: ToolCatalog) -> None:
        assert catalog.hot_path() == ["audit"]


class TestSearch:
    def test_match_by_name(self, catalog: ToolCatalog) -> None:
        hits = catalog.search("audit")
        assert [h["name"] for h in hits] == ["audit"]
        assert hits[0]["domain"] == "audit"

    def test_match_by_tag(self, catalog: ToolCatalog) -> None:
        assert catalog.search("quality")[0]["name"] == "audit"
        assert catalog.search("citation")[0]["name"] == "bib_resolve"

    def test_empty_query_lists_all(self, catalog: ToolCatalog) -> None:
        assert len(catalog.search("")) == 3

    def test_domain_filter(self, catalog: ToolCatalog) -> None:
        hits = catalog.search("", domain="bib")
        assert [h["name"] for h in hits] == ["bib_resolve"]

    def test_no_match_returns_empty(self, catalog: ToolCatalog) -> None:
        assert catalog.search("zzz-nope") == []

    def test_limit_respected(self, catalog: ToolCatalog) -> None:
        assert len(catalog.search("", limit=1)) == 1


class TestDescribe:
    def test_params_and_required(self, catalog: ToolCatalog) -> None:
        d = catalog.describe("audit")
        names = [p["name"] for p in d["params"]]
        assert "path" in names and "category" in names
        path = next(p for p in d["params"] if p["name"] == "path")
        assert path["required"] is False
        assert path["annotation"] == "str"

    def test_required_param_flagged(self, catalog: ToolCatalog) -> None:
        d = catalog.describe("bib_resolve")
        ref = next(p for p in d["params"] if p["name"] == "ref")
        assert ref["required"] is True

    def test_unknown_raises(self, catalog: ToolCatalog) -> None:
        with pytest.raises(UnknownToolError, match="Known tools"):
            catalog.describe("nope")


class TestCall:
    def test_text_result_returned(self, catalog: ToolCatalog) -> None:
        assert catalog.call("audit", {"path": "."}) == "audit: 90/100"

    def test_data_rendered_when_no_text(self, catalog: ToolCatalog) -> None:
        out = catalog.call("bib_resolve", {"ref": "x"})
        assert "doi: 10.x" in out
        assert "success: True" in out

    def test_plain_callable(self, catalog: ToolCatalog) -> None:
        assert "ok" in catalog.call("plain_tool", {})

    def test_unknown_raises(self, catalog: ToolCatalog) -> None:
        with pytest.raises(UnknownToolError):
            catalog.call("nope", {})

    def test_bad_kwargs_propagate_typeerror(self, catalog: ToolCatalog) -> None:
        # ref is required; calling without it must raise TypeError (the facade
        # tool layer turns this into a param hint).
        with pytest.raises(TypeError):
            catalog.call("bib_resolve", {})


class TestFacadeTypeValidation:
    def test_rejects_mistyped_list_item_before_dispatch(self) -> None:
        """AC1: a non-string list item raises validation before execute."""
        tool = _TypedListTool()
        typed_catalog = _catalog(typed_list=tool)

        with pytest.raises((TypeError, ValidationError, ToolError)):
            typed_catalog.call("typed_list", {"symbols": [123]})

        assert tool.calls == 0

    def test_rejects_mistyped_scalar_before_dispatch(self) -> None:
        """AC2: a scalar mismatch raises validation before execute."""
        tool = _TypedScalarTool()
        typed_catalog = _catalog(typed_scalar=tool)

        with pytest.raises((TypeError, ValidationError, ToolError)):
            typed_catalog.call("typed_scalar", {"count": "not-an-int"})

        assert tool.calls == 0

    def test_coerces_bool_to_int_before_dispatch(self) -> None:
        """AC5: a pydantic-coercible JSON list reaches execute as a list."""
        tool = _CoercibleIntTool()
        typed_catalog = _catalog(coercible_int=tool)

        typed_catalog.call("coercible_int", {"items": True})

        assert tool.received == [1]
        assert type(tool.received[0]) is int


class TestCallFailureContract:
    """AXM-2026: call() must mirror the wrapper's failure-preserving contract."""

    @dataclass
    class _Res:
        success: bool
        data: dict[str, Any] = field(default_factory=dict)
        text: str | None = None
        error: str | None = None

    class _NoSuccessRes:
        """A result object that lacks a ``success`` attribute entirely."""

        def __init__(self, data: dict[str, Any], error: str | None = None) -> None:
            self.data = data
            self.text: str | None = None
            self.error = error

    def _catalog_for(self, result: object) -> ToolCatalog:
        class _FakeTool:
            def execute(self, **_kwargs: Any) -> object:
                return result

        return _catalog(fake=_FakeTool())

    def test_call_failure_preserves_signal(self) -> None:
        """AC2: a failing ToolResult never reaches the caller as bare text.

        The signal is now carried by the status line the wrapper composes
        rather than by a flattened ``success: False`` key, so the failure and
        its ``error`` stay unmistakable while the tool's own diagnostic text
        — the part a reader actually needs — survives alongside them.
        """
        res = self._Res(
            success=False,
            error="boom",
            text="human readable failure message",
            data={"detail": "x"},
        )
        out = self._catalog_for(res).call("fake")

        assert out.startswith("\u2717 ")
        assert "boom" in out
        assert out != "human readable failure message"
        assert "human readable failure message" in out

    def test_call_success_short_circuits_to_text(self) -> None:
        """AC2: a successful ToolResult with text still short-circuits to it."""
        res = self._Res(success=True, text="all good", data={"k": "v"})
        assert self._catalog_for(res).call("fake") == "all good"

    def test_call_missing_success_not_defaulted_true(self) -> None:
        """AC3: a result lacking a success attr is treated as failure, not True."""
        res = self._NoSuccessRes(data={"detail": "y"}, error="oops")
        out = self._catalog_for(res).call("fake")

        assert "success: True" not in out
        assert "success: False" in out

    def test_call_reserved_key_collision_relocated(self) -> None:
        """AC4: a data key colliding with a reserved envelope key is relocated."""
        res = self._Res(
            success=False,
            error="real error",
            data={"success": "shadow", "payload": 1},
        )
        out = self._catalog_for(res).call("fake")

        assert "success: False" in out
        assert "data_success: shadow" in out
        assert "error: real error" in out


class TestSingleExecutionPath:
    """The facade path (``call``/``acall``) runs through the SAME wrapper as the
    direct MCP path — so tracing, exception flattening and locking are invariant
    regardless of how a tool is reached. Each test here fails on the pre-fix code
    that executed ``_exec_fn(tool)(**args)`` directly, bypassing the wrapper.
    """

    def test_call_emits_a_trace(self) -> None:
        """AXM invariant '1 call = 1 trace': the facade path traces too.

        The old direct-exec path emitted NO trace (it never touched the
        wrapper). Delegating to the sync wrapper restores it.
        """
        cat = _catalog(audit=_AuditTool())
        with patch("axm_mcp.wrapping.log_external_step") as mock_log:
            cat.call("audit", {"path": "."})
        mock_log.assert_called_once()
        assert mock_log.call_args[0][0] == "audit"

    def test_call_flattens_a_raised_exception(self) -> None:
        """A tool raising ValueError is flattened, not propagated.

        The old direct-exec path let a ``ValueError`` escape to the caller
        (a raw MCP protocol error); the wrapper turns it into the AXM error
        envelope — the identical contract the direct path already had.
        """

        class _Boom:
            def execute(self, **_kwargs: Any) -> ToolResult:
                raise ValueError("kaboom")

        out = _catalog(boom=_Boom()).call("boom")
        assert "success: False" in out
        assert "ValueError" in out
        assert "kaboom" in out

    @pytest.mark.asyncio
    async def test_acall_matches_call_contract(self) -> None:
        """``acall`` (HTTP entry) renders identically to ``call`` in stdio."""
        cat = _catalog(audit=_AuditTool())
        args = {"path": "."}
        assert await cat.acall("audit", args) == cat.call("audit", args)

    @pytest.mark.asyncio
    async def test_acall_holds_lock_for_git_tool(self) -> None:
        """AXM lock invariant via the facade: two concurrent ``acall`` on the
        same git repo path serialize (proving the lock is HELD on this path).

        The old direct-exec path never acquired ``_git_lock`` — the two calls
        would interleave. Delegating to the async wrapper serializes them.
        """
        import axm_mcp.wrapping as _wrapping

        order: list[str] = []

        class _SlowGit:
            def execute(self, *, path: str = "", **_kwargs: Any) -> ToolResult:
                import time

                order.append("start")
                time.sleep(0.05)
                order.append("end")
                return ToolResult(success=True, data={"path": path}, text="ok")

        cat = _catalog(git_commit=_SlowGit())
        original = _wrapping._HTTP_MODE
        try:
            _wrapping._HTTP_MODE = True
            await asyncio.gather(
                cat.acall("git_commit", {"path": "/repo"}),
                cat.acall("git_commit", {"path": "/repo"}),
            )
        finally:
            _wrapping._HTTP_MODE = original
        # Serialized: first call ends before the second starts.
        assert order == ["start", "end", "start", "end"]


class TestParamHint:
    def test_lists_params(self, catalog: ToolCatalog) -> None:
        hint = catalog.param_hint("audit")
        assert "path: str" in hint

    def test_unknown_returns_empty(self, catalog: ToolCatalog) -> None:
        assert catalog.param_hint("nope") == ""


class TestCapabilities:
    def test_grouped_by_domain(self, catalog: ToolCatalog) -> None:
        caps = catalog.capabilities()
        assert caps["audit"] == ["audit"]
        assert caps["bib"] == ["bib_resolve"]
        assert caps["(ungrouped)"] == ["plain_tool"]

    def test_single_domain_filter(self, catalog: ToolCatalog) -> None:
        assert catalog.capabilities(domain="audit") == {"audit": ["audit"]}


class TestTextRenderers:
    def test_render_describe_emits_contract_and_verbatim_docstring(self) -> None:
        """AC1: describe text has its header, params, and verbatim docstring."""
        docstring = "Commit staged changes.\n\nArgs:\n    path: Repository root."
        spec = {
            "name": "git_commit",
            "summary": "Commit staged changes.",
            "domain": "git",
            "tags": ["commit", "vcs"],
            "docstring": docstring,
            "params": [
                {
                    "name": "path",
                    "annotation": "str",
                    "required": False,
                    "default": "'.'",
                },
                {
                    "name": "message",
                    "annotation": "str",
                    "required": True,
                    "default": None,
                },
            ],
        }

        rendered = catalog_module.render_describe(spec)

        assert isinstance(rendered, str)
        assert rendered.splitlines()[0] == "git_commit | git | commit vcs"
        assert "path: str = '.'" in rendered.splitlines()
        assert "message: str" in rendered.splitlines()
        assert rendered.endswith(docstring)

    def test_render_describe_omits_standalone_summary(self) -> None:
        """AC2: the docstring first line is not duplicated as summary metadata."""
        spec = {
            "name": "git_commit",
            "summary": "Commit staged changes.",
            "domain": "git",
            "tags": ["commit"],
            "docstring": "Commit staged changes.",
            "params": [],
        }

        rendered = catalog_module.render_describe(spec)

        assert not any(line.startswith("summary:") for line in rendered.splitlines())
        assert rendered.count("Commit staged changes.") == 1

    def test_render_unknown_suggests_without_dumping_catalog(self) -> None:
        """AC3: unknown-tool text gives compact difflib near-matches only."""
        catalog = _catalog(
            git_commit=_plain,
            ticket_create=_plain,
            distant_catalog_tool=_plain,
        )

        rendered = catalog_module.render_unknown("git_commt", catalog)

        assert "Did you mean:" in rendered
        assert "git_commit" in rendered
        assert "distant_catalog_tool" not in rendered
        assert ", ".join(catalog.names()) not in rendered
        assert len(rendered) < 200

    def test_render_search_headers_count_and_lists_hits(
        self, catalog: ToolCatalog
    ) -> None:
        """AC4: search text has a count header and one informative hit line."""
        results = catalog.search("")

        rendered = catalog_module.render_search(results)
        lines = rendered.splitlines()

        assert lines[0] == f"axm_search | {len(results)} hits"
        assert len(lines[1:]) == len(results)
        for result, line in zip(results, lines[1:], strict=True):
            assert str(result["name"]) in line
            assert str(result["summary"]) in line

    def test_render_capabilities_inlines_each_domain(self) -> None:
        """AC5: every domain occupies one line with space-separated tools."""
        domains = {
            "git": ["git_commit", "git_preflight"],
            "audit": ["audit", "verify"],
        }

        rendered = catalog_module.render_capabilities(domains)
        lines = rendered.splitlines()

        assert len(lines) == len(domains)
        assert "git: git_commit git_preflight" in lines
        assert "audit: audit verify" in lines

    def test_render_list_tools_headers_count_and_lists_descriptions(self) -> None:
        """AC6: tool listing has its count header and one description per line."""
        tools = [
            {"name": "audit", "description": "Audit project quality."},
            {"name": "git_commit", "description": "Commit staged changes."},
        ]

        rendered = catalog_module.render_list_tools(tools)

        assert rendered.splitlines() == [
            "list_tools | 2 tools",
            "audit — Audit project quality.",
            "git_commit — Commit staged changes.",
        ]
