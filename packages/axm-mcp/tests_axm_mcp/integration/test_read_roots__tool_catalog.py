from __future__ import annotations

import json
from typing import cast

import pytest
from axm_ast.tools.inspect import InspectTool
from axm_edit.tools.read_file import ReadFileTool
from axm_edit.tools.write_file import WriteFileTool

from axm_mcp.discovery import ToolEntry
from axm_mcp.facade.catalog import ToolCatalog
from axm_mcp.session_contracts import parse_write_contract_header

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("relative", [True, False])
def test_read_only_land_tree_is_readable_but_not_writable(
    tmp_path, monkeypatch, relative
):
    tree = tmp_path / "delivered"
    (tree / "src" / "example").mkdir(parents=True)
    (tree / "pyproject.toml").write_text('[project]\nname="example"\nversion="0.1.0"\n')
    source = tree / "src" / "example" / "__init__.py"
    source.write_text("class Example:\n    pass\n")
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)
    contract = parse_write_contract_header(
        json.dumps(
            {
                "execution_root": str(tree),
                "read_roots": [str(tree)],
                "allowed_prefixes": [],
                "markdown_only_prefixes": [],
                "read_path_aliases": [(str(tmp_path / "lane"), str(tree))],
            }
        )
    )
    catalog = ToolCatalog(
        {
            name: cast("ToolEntry", tool)
            for name, tool in {
                "ast_inspect": InspectTool(),
                "read_file": ReadFileTool(),
                "write_file": WriteFileTool(),
            }.items()
        },
        shared_mode=True,
        write_contract_resolver=lambda: contract,
    )
    path = "." if relative else str(tree)
    assert "class Example" in catalog.call(
        "ast_inspect",
        {"path": path, "symbol": "Example", "source": True},
    )
    assert "class Example" in catalog.call(
        "read_file",
        {"path": path, "file": "src/example/__init__.py"},
    )
    for tool, arguments in [
        ("ast_inspect", {"path": str(outside), "symbol": "Example"}),
        ("read_file", {"path": str(outside), "file": "secret.txt"}),
        (
            "write_file",
            {"path": path, "file": "src/example/__init__.py", "content": "changed"},
        ),
    ]:
        assert "success: False" in catalog.call(tool, arguments)
    assert source.read_text() == "class Example:\n    pass\n"
    assert "class Example" in catalog.call(
        "ast_inspect",
        {
            "path": str(tmp_path / "lane"),
            "symbol": "Example",
            "source": True,
        },
    )
