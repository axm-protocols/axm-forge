"""Unit tests for the facade ToolCatalog (no I/O, fake tools)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

import pytest
from axm.tools.base import ToolResult

from axm_mcp.discovery import ToolEntry
from axm_mcp.facade.catalog import ToolCatalog, UnknownToolError


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


def _plain(**kwargs: Any) -> dict[str, Any]:
    """Plain dispatcher tool."""
    return {"ok": 1}


def _catalog(**tools: object) -> ToolCatalog:
    """Build a catalog from fake tools, casting to the ToolEntry contract."""
    return ToolCatalog({k: cast(ToolEntry, v) for k, v in tools.items()})


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
        """AC2: a failing ToolResult never loses success=False/error to bare text."""
        res = self._Res(
            success=False,
            error="boom",
            text="human readable failure message",
            data={"detail": "x"},
        )
        out = self._catalog_for(res).call("fake")

        assert "success: False" in out
        assert "error: boom" in out
        assert out != "human readable failure message"

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
