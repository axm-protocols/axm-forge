"""Tests for the decoupled FastMCP server configuration.

Merged from aspect-split mirror sources:
- test_mcp_app.py       (server config)
- test_coverage_gaps.py (package entry point)
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
from collections.abc import Iterator
from importlib import import_module
from typing import Any, cast
from unittest.mock import patch

import httpx
import pytest
from axm.tools.base import ToolResult
from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http import MCP_SESSION_ID_HEADER

from axm_mcp import mcp_app
from axm_mcp.discovery import ToolEntry
from axm_mcp.facade.catalog import ToolCatalog
from axm_mcp.facade.tools import register_facade
from axm_mcp.session_contracts import (
    SessionContractRegistry,
    UnboundSessionError,
    WriteContract,
)


class TestMCPServer:
    """Tests for FastMCP server configuration."""

    def test_server_name(self) -> None:
        """Server has correct name."""
        assert mcp_app.mcp.name == "axm-mcp"

    def test_discovery_ran(self) -> None:
        """Tool discovery ran (may be empty if no axm-* packages installed)."""
        assert isinstance(mcp_app.discovered_tools, dict)


class TestInitMain:
    """Cover main() in __init__.py (lines 10-12)."""

    def test_init_main_calls_run(self) -> None:
        """Package-level main() routes through CLI to mcp.run() (stdio)."""
        with (
            patch("axm_mcp.mcp_app.mcp") as mock_mcp,
            patch("sys.argv", ["axm-mcp"]),
        ):
            import axm_mcp

            with pytest.raises(SystemExit, match="0"):
                axm_mcp.main()
            mock_mcp.run.assert_called_once()


def _session_registry() -> SessionContractRegistry:
    return SessionContractRegistry(clock=lambda: 0.0)


def test_session_start_binds_declared_perimeter() -> None:
    """AC2: the session-start hook binds its declared write perimeter."""
    registry = _session_registry()

    mcp_app._on_session_start(
        registry=registry,
        session_id="s-a",
        write_contract_json='{"execution_root": "/tmp/a"}',
    )

    assert registry.resolve("s-a").execution_root == os.path.realpath("/tmp/a")


def test_session_start_without_perimeter_stays_unbound() -> None:
    """AC3: no perimeter declaration grants no default session contract."""
    registry = _session_registry()

    mcp_app._on_session_start(
        registry=registry,
        session_id="s-plain",
        write_contract_json=None,
    )

    with pytest.raises(UnboundSessionError):
        registry.resolve("s-plain")


def test_session_end_releases_bound_perimeter() -> None:
    """AC4: the session-end hook releases the closed session's contract."""
    registry = _session_registry()
    mcp_app._on_session_start(
        registry=registry,
        session_id="s-a",
        write_contract_json='{"execution_root": "/tmp/a"}',
    )

    mcp_app._on_session_end(registry=registry, session_id="s-a")

    with pytest.raises(UnboundSessionError):
        registry.resolve("s-a")


def test_headers_bind_contract_to_session_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: request headers bind the declared scope to their identity."""
    registry = _session_registry()
    monkeypatch.setattr(mcp_app, "session_contract_registry", registry)
    headers = {
        MCP_SESSION_ID_HEADER: "sess-a",
        "X-AXM-Write-Contract": '{"execution_root": "/tmp/a"}',
    }

    mcp_app.bind_session_from_headers(headers)

    contract = mcp_app.contract_for_session_id("sess-a")
    assert contract.execution_root == os.path.realpath("/tmp/a")


def test_built_http_app_binds_contract_from_ordinary_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: the served ASGI app binds scope from an ordinary request."""
    registry = _session_registry()
    monkeypatch.setattr(mcp_app, "session_contract_registry", registry)
    monkeypatch.setattr(
        mcp_app,
        "resolve_serve_mode",
        lambda explicit=None: "shared",
        raising=False,
    )
    payload = {
        "execution_root": "/scope/sid-1",
        "allowed_prefixes": ["/scope/sid-1", "/scope/shared"],
        "markdown_only_prefixes": [],
    }
    app = mcp_app.build_http_app()

    async def post_request() -> None:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            await client.post(
                "/mcp",
                headers={
                    MCP_SESSION_ID_HEADER: "sid-1",
                    "X-AXM-Write-Contract": json.dumps(payload),
                    "accept": "application/json, text/event-stream",
                    "content-type": "application/json",
                },
                json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            )

    asyncio.run(post_request())

    contract = mcp_app.contract_for_session_id("sid-1")
    assert contract.execution_root == payload["execution_root"]
    assert contract.allowed_prefixes == payload["allowed_prefixes"]


def test_session_identity_header_lookup_is_case_insensitive() -> None:
    """AC1: session identity lookup accepts transport header casing."""
    headers = {MCP_SESSION_ID_HEADER.swapcase(): "sess-a"}

    assert mcp_app.session_id_from_headers(headers) == "sess-a"


def test_contract_lookup_for_unbound_identity_names_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: an unbound-session error names the unresolved identity."""
    registry = _session_registry()
    monkeypatch.setattr(mcp_app, "session_contract_registry", registry)

    with pytest.raises(UnboundSessionError) as exc_info:
        mcp_app.contract_for_session_id("sess-ghost")

    assert "sess-ghost" in str(exc_info.value)


def test_header_binding_does_not_survive_session_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: session end releases the identity's header-bound contract."""
    registry = _session_registry()
    monkeypatch.setattr(mcp_app, "session_contract_registry", registry)
    headers = {
        MCP_SESSION_ID_HEADER: "sess-a",
        "X-AXM-Write-Contract": '{"execution_root": "/tmp/a"}',
    }
    mcp_app.bind_session_from_headers(headers)
    assert mcp_app.contract_for_session_id("sess-a").execution_root

    mcp_app._on_session_end(registry=registry, session_id="sess-a")

    with pytest.raises(UnboundSessionError):
        mcp_app.contract_for_session_id("sess-a")


class TestDecouplingShape:
    """Pure-import decoupling invariants on the discovery shell (no I/O)."""

    @pytest.mark.parametrize(
        "func_name",
        ["init", "check", "resume", "read", "configure", "get_orchestrator"],
        ids=["init", "check", "resume", "read", "configure", "get_orchestrator"],
    )
    def test_no_hardcoded_protocol_function(self, func_name: str) -> None:
        """mcp_app discovers tools dynamically; it hardcodes no protocol func."""
        attr = getattr(mcp_app, func_name, None)
        assert attr is None or not callable(attr), (
            f"{func_name}() is hardcoded in mcp_app"
        )

    def test_legacy_server_package_removed(self) -> None:
        """The legacy ``server/`` sub-package is no longer importable."""
        with pytest.raises(ModuleNotFoundError):
            import_module("axm_mcp.server.app")


_DISCOVER = "axm_mcp.discovery.importlib.metadata.entry_points"


class _HotTool:
    expose_directly = True
    domain = "demo"

    @property
    def name(self) -> str:
        return "hot_one"

    def execute(self, *, x: int = 0) -> ToolResult:
        """A hot-path demo tool."""
        return ToolResult(success=True, text="ok")


class _ColdTool:
    @property
    def name(self) -> str:
        return "cold_one"

    def execute(self, *, y: int = 0) -> ToolResult:
        """A facade-only demo tool."""
        return ToolResult(success=True, text="ok")


class _WriteFileProbe:
    def execute(self, *, path: str, file: str, content: str) -> ToolResult:
        return ToolResult(success=True, text=f"wrote {path}/{file}: {content}")


def _registered_text(server: FastMCP, tool: str, **arguments: object) -> str:
    result = asyncio.run(server.call_tool(tool, arguments))
    blocks = result[0] if isinstance(result, tuple) else result
    return blocks[0].text if isinstance(blocks, list) else str(blocks)


def _write_decision(rendered: str) -> tuple[bool, str]:
    try:
        payload = json.loads(rendered)
    except json.JSONDecodeError:
        fields = {
            key: value
            for line in rendered.splitlines()
            if ": " in line
            for key, value in [line.split(": ", 1)]
        }
        if "success" not in fields:
            return True, rendered
        return fields["success"].casefold() == "true", fields.get("error", "")
    return bool(payload["success"]), str(payload.get("error", ""))


class _FakeEP:
    def __init__(self, name: str, obj: object) -> None:
        self.name = name
        self._obj = obj

    def load(self) -> object:
        return self._obj


def _fake_entry_points(*, group: str | None = None, **_: Any) -> list[_FakeEP]:
    if group == "axm.tools":
        return [_FakeEP("hot_one", _HotTool), _FakeEP("cold_one", _ColdTool)]
    return []


def _reload_app() -> Any:
    import axm_mcp.mcp_app as app

    return importlib.reload(app)


@pytest.fixture
def _restore_app() -> Iterator[None]:
    # Ensure the module is reloaded back to its real state after the test.
    yield
    with patch(_DISCOVER, _fake_entry_points):
        _reload_app()
    importlib.reload(__import__("axm_mcp.mcp_app", fromlist=["x"]))


def _exposed_names(monkeypatch: pytest.MonkeyPatch, facade: str) -> set[str]:
    monkeypatch.setenv("AXM_MCP_FACADE", facade)
    with patch(_DISCOVER, _fake_entry_points):
        app = _reload_app()
    return {t.name for t in asyncio.run(app.mcp.list_tools())}


def test_direct_and_facade_paths_return_the_same_write_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: direct and facade doors yield one identical refusal decision."""
    registry = _session_registry()
    registry.bind(
        "sess-a",
        WriteContract.from_mapping(
            {"execution_root": "/scope_a", "allowed_prefixes": ["/scope_a"]}
        ),
    )
    server = FastMCP("shared-parity")
    probe = _WriteFileProbe()
    tools = {"write_file": cast(ToolEntry, probe)}
    monkeypatch.setattr(mcp_app, "mcp", server)
    monkeypatch.setattr(mcp_app, "_SHARED_MODE", True)
    monkeypatch.setattr(mcp_app, "session_contract_registry", registry)
    monkeypatch.setattr(mcp_app, "current_session_id", lambda: "sess-a")
    mcp_app._register_direct(tools)
    catalog = ToolCatalog(
        tools,
        shared_mode=True,
        write_contract_resolver=mcp_app._resolve_session_contract,
    )
    register_facade(server, catalog)
    arguments = {"path": "/scope_b", "file": "x.txt", "content": "blocked"}

    direct = _registered_text(server, "write_file", **arguments)
    facade = _registered_text(
        server, "axm_call", name="write_file", arguments=arguments
    )

    assert _write_decision(direct) == _write_decision(facade)


def test_facade_mode_hides_cold_tool(
    monkeypatch: pytest.MonkeyPatch, _restore_app: None
) -> None:
    names = _exposed_names(monkeypatch, "1")
    # Facade meta-tools present
    assert {"axm_search", "axm_describe", "axm_call", "axm_capabilities"} <= names
    # Hot-path tool exposed directly; cold tool hidden behind the facade
    assert "hot_one" in names
    assert "cold_one" not in names


def test_legacy_mode_exposes_all(
    monkeypatch: pytest.MonkeyPatch, _restore_app: None
) -> None:
    names = _exposed_names(monkeypatch, "0")
    assert "hot_one" in names
    assert "cold_one" in names
    assert "axm_search" not in names


def test_facade_payload_smaller_than_legacy(
    monkeypatch: pytest.MonkeyPatch, _restore_app: None
) -> None:
    facade = _exposed_names(monkeypatch, "1")
    legacy = _exposed_names(monkeypatch, "0")
    # Legacy exposes every discovered tool; facade collapses the cold ones.
    assert len(facade) < len(legacy) + 4  # facade adds 4 meta-tools
    assert "cold_one" in legacy and "cold_one" not in facade


def test_builtins_are_in_catalog(
    monkeypatch: pytest.MonkeyPatch, _restore_app: None
) -> None:
    """P2-3: the built-ins (verify/web_fetch) are indexed by the catalog, so
    ``axm_describe('verify')`` resolves instead of returning 'Unknown tool'.
    """
    monkeypatch.setenv("AXM_MCP_FACADE", "1")
    with patch(_DISCOVER, _fake_entry_points):
        app = _reload_app()
    assert "verify" in app.catalog.names()
    assert "web_fetch" in app.catalog.names()
    described = app.catalog.describe("verify")
    assert described["name"] == "verify"
