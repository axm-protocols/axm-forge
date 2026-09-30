"""MCP exposure routes share dependency authority without session leakage."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import cast

import pytest
from axm.tools.dependency_reads import dependency_sources
from axm.tools.write_scope import WriteContract
from axm_edit.tools.read_file import ReadFileTool

from axm_mcp.discovery import ToolEntry
from axm_mcp.facade.catalog import ToolCatalog
from axm_mcp.wrapping import build_wrappers

pytestmark = pytest.mark.integration


def _contract(root: Path, dependencies: list[str]) -> WriteContract:
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname="consumer"\nversion="0"\ndependencies='
        + str(dependencies).replace("'", '"')
        + "\n"
    )
    return WriteContract.from_mapping(
        {
            "execution_root": str(root),
            "allowed_prefixes": [],
            "dependency_environment": {
                "interpreter": sys.executable,
                "package_root": str(root),
                "pythonpath": [],
            },
        }
    )


def test_direct_and_facade_reads_use_the_same_dependency_root(tmp_path: Path) -> None:
    contract = _contract(tmp_path / "lane", ["axm"])
    assert contract.dependency_environment is not None
    resolved = dependency_sources(contract.dependency_environment).resolve_symbol(
        "axm.tools.node"
    )
    assert resolved is not None
    tool = ReadFileTool()
    direct, _ = build_wrappers(
        "read_file", tool, shared_mode=True, write_contract_resolver=lambda: contract
    )
    catalog = ToolCatalog(
        {"read_file": cast("ToolEntry", tool)},
        shared_mode=True,
        write_contract_resolver=lambda: contract,
    )
    arguments = {"path": ".", "file": str(resolved[0])}
    assert direct(**arguments) == catalog.call("read_file", arguments)
    assert "load_tool" in catalog.call("read_file", arguments)


def test_concurrent_sessions_keep_separate_dependency_closures(tmp_path: Path) -> None:
    allowed = _contract(tmp_path / "allowed", ["axm"])
    denied = _contract(tmp_path / "denied", [])
    assert allowed.dependency_environment is not None
    resolved = dependency_sources(allowed.dependency_environment).resolve_symbol(
        "axm.tools.node"
    )
    assert resolved is not None

    def catalog_for(contract: WriteContract) -> ToolCatalog:
        return ToolCatalog(
            {"read_file": cast("ToolEntry", ReadFileTool())},
            shared_mode=True,
            write_contract_resolver=lambda: contract,
        )

    catalogs = [catalog_for(c) for c in (allowed, denied)]

    async def read() -> list[str]:
        return list(
            await asyncio.gather(
                *(
                    catalog.acall("read_file", {"path": ".", "file": str(resolved[0])})
                    for catalog in catalogs
                )
            )
        )

    granted, refused = asyncio.run(read())
    assert "load_tool" in granted
    assert "outside the allowed prefixes" in refused
