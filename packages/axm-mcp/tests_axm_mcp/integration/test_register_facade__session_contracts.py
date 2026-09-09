"""Integration coverage for facade dispatch under session write contracts."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast

import pytest
from axm.tools.base import ToolResult
from mcp.server.mcpserver import MCPServer

from axm_mcp import mcp_app
from axm_mcp.discovery import ToolEntry
from axm_mcp.facade.catalog import ToolCatalog
from axm_mcp.facade.tools import register_facade
from axm_mcp.session_contracts import SessionContractRegistry, WriteContract


class _RealWriteFileProbe:
    def execute(self, *, path: str, file: str, content: str) -> ToolResult:
        target = Path(path) / file
        target.write_text(content, encoding="utf-8")
        return ToolResult(success=True, text=str(target))


def _call_text(server: MCPServer, tool: str, **arguments: object) -> str:
    result = asyncio.run(server.call_tool(tool, arguments))
    blocks = getattr(result, "content", None)
    if blocks is None:
        blocks = result[0] if isinstance(result, tuple) else result
    return blocks[0].text if isinstance(blocks, list) else str(blocks)


@pytest.mark.integration
def test_facade_session_a_cannot_write_in_session_b_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: facade dispatch cannot leak a real write into another session."""
    directory_a = tmp_path / "session-a"
    directory_b = tmp_path / "session-b"
    directory_a.mkdir()
    directory_b.mkdir()
    target = directory_b / "leak.txt"
    registry = SessionContractRegistry(clock=lambda: 0.0)
    registry.bind(
        "sess-a",
        WriteContract.from_mapping(
            {
                "execution_root": str(directory_a),
                "allowed_prefixes": [str(directory_a)],
            }
        ),
    )
    registry.bind(
        "sess-b",
        WriteContract.from_mapping(
            {
                "execution_root": str(directory_b),
                "allowed_prefixes": [str(directory_b)],
            }
        ),
    )
    monkeypatch.setattr(mcp_app, "session_contract_registry", registry)
    monkeypatch.setattr(mcp_app, "current_session_id", lambda: "sess-a")
    catalog = ToolCatalog(
        {"write_file": cast(ToolEntry, _RealWriteFileProbe())},
        shared_mode=True,
        write_contract_resolver=mcp_app._resolve_session_contract,
    )
    server = MCPServer("shared-facade-integration")
    register_facade(server, catalog)

    rendered = _call_text(
        server,
        "axm_call",
        name="write_file",
        arguments={
            "path": str(directory_b),
            "file": target.name,
            "content": "cross-session leak",
        },
    )

    assert "success: False" in rendered
    assert not target.exists()
