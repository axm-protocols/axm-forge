"""Opt-in, read-only replay of the persisted DEV-55 agent tool context."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
from axm.tools.dependency_reads import dependency_sources
from axm.tools.write_scope import WriteContract
from axm_ast.tools.inspect import InspectTool
from axm_edit.tools.batch_edit import BatchEditTool
from axm_edit.tools.read_file import ReadFileTool

from axm_mcp.facade.catalog import ToolCatalog
from axm_mcp.wrapping import build_wrappers

pytestmark = pytest.mark.e2e


def test_dev55_dependency_reads_and_write_refusal() -> None:
    context_path = os.environ.get("AXM_DEPENDENCY_REPLAY_CONTEXT")
    if not context_path:
        pytest.skip("requires a persisted operator-selected lane context")
    contract = WriteContract.from_mapping(json.loads(Path(context_path).read_text()))
    assert contract.dependency_environment is not None
    resolved = dependency_sources(contract.dependency_environment).resolve_symbol(
        "axm.tools.node"
    )
    assert resolved is not None
    source = resolved[0]
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    tools = {
        "ast_inspect": InspectTool(),
        "read_file": ReadFileTool(),
        "batch_edit": BatchEditTool(),
    }
    catalog = ToolCatalog(
        tools, shared_mode=True, write_contract_resolver=lambda: contract
    )
    results = {}
    for symbol in ("axm.tools.node", "axm.tools.node.load_tool"):
        direct, _ = build_wrappers(
            "ast_inspect",
            tools["ast_inspect"],
            shared_mode=True,
            write_contract_resolver=lambda: contract,
        )
        result = direct(path=contract.execution_root, symbol=symbol, source=True)
        assert isinstance(result, str) and "load_tool" in result, result
        assert "not found" not in result[:200], result
        results[symbol] = "read succeeded"
    read = catalog.call(
        "read_file", {"path": contract.execution_root, "file": str(source)}
    )
    assert "load_tool" in read and "ESCAPE" not in read[:200], read
    write = catalog.call(
        "batch_edit",
        {
            "path": contract.execution_root,
            "operations": [
                {
                    "op": "replace",
                    "file": str(source),
                    "edits": [{"old": "# impossible", "new": "# forbidden"}],
                }
            ],
        },
    )
    assert "outside the allowed prefixes" in write, write
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    results.update(source=str(source), read_file="read succeeded", write_refusal=write)
    report = os.environ.get("AXM_DEPENDENCY_REPLAY_REPORT")
    if report:
        Path(report).write_text(json.dumps(results, indent=2) + "\n")
