"""Shared sessions resolve real read/write tools independently of server cwd."""

from __future__ import annotations

from pathlib import Path

import pytest
from axm.tools.write_scope import WriteContract
from axm_ast.tools.context import ContextTool
from axm_edit.tools.write_file import WriteFileTool

from axm_mcp.discovery import ToolEntry
from axm_mcp.wrapping import _SyncWrapper, build_wrappers

pytestmark = pytest.mark.integration


def _wrapper(name: str, tool: ToolEntry, root: Path | None) -> _SyncWrapper:
    contract = (
        WriteContract.from_mapping(
            {"execution_root": str(root), "allowed_prefixes": [str(root)]}
        )
        if root is not None
        else None
    )
    return build_wrappers(
        name, tool, shared_mode=True, write_contract_resolver=lambda: contract
    )[0]


@pytest.fixture
def trees(tmp_path, monkeypatch):
    server = tmp_path / "server"
    candidate = tmp_path / "candidate"
    server.mkdir()
    (candidate / "src" / "candidate_pkg").mkdir(parents=True)
    (candidate / "src" / "candidate_pkg" / "__init__.py").write_text("VALUE = 1\n")
    (candidate / "pyproject.toml").write_text(
        '[project]\nname = "candidate-pkg"\nversion = "0.1.0"\n'
    )
    monkeypatch.chdir(server)
    return server, candidate


def test_ast_context_uses_session_root(trees):
    server, root = trees
    result = _wrapper("ast_context", ContextTool(), root)(path=".", depth=0)
    assert isinstance(result, str), result
    assert "candidate_pkg" in result
    assert "server" not in result
    assert not (server / "src").exists()


@pytest.mark.parametrize("implicit", [False, True])
def test_write_file_uses_identical_authorized_and_executed_root(trees, implicit):
    server, root = trees
    wrapper = _wrapper("write_file", WriteFileTool(), root)
    result = wrapper(
        file="x.py", content="VALUE = 2\n", **({} if implicit else {"path": "."})
    )
    assert (root / "x.py").read_text() == "VALUE = 2\n", result
    assert not (server / "x.py").exists()


@pytest.mark.parametrize("path", ["..", "../server"])
def test_relative_root_escape_is_refused(trees, path):
    server, root = trees
    result = _wrapper("write_file", WriteFileTool(), root)(
        path=path, file="x.py", content="bad"
    )
    assert isinstance(result, dict) and result["success"] is False
    assert not (server / "x.py").exists()


def test_symlink_escape_is_refused(trees):
    server, root = trees
    (root / "escape").symlink_to(server, target_is_directory=True)
    result = _wrapper("write_file", WriteFileTool(), root)(
        path=".", file="escape/x.py", content="bad"
    )
    assert isinstance(result, dict) and result["success"] is False
    assert not (server / "x.py").exists()


def test_unrooted_session_refuses_relative_reads_and_writes(trees):
    for name, tool, kwargs in [
        ("ast_context", ContextTool(), {"path": "."}),
        ("write_file", WriteFileTool(), {"file": "x.py", "content": "bad"}),
    ]:
        result = _wrapper(name, tool, None)(**kwargs)
        assert isinstance(result, dict) and result["success"] is False
        assert "execution_root" in result["error"]


def test_absolute_write_is_limited_to_session_root(trees):
    server, root = trees
    wrapper = _wrapper("write_file", WriteFileTool(), root)
    wrapper(path=str(root), file=str(root / "x.py"), content="allowed")
    assert (root / "x.py").read_text() == "allowed"
    result = wrapper(path=str(server), file="outside.py", content="bad")
    assert isinstance(result, dict) and result["success"] is False
    assert not (server / "outside.py").exists()


@pytest.mark.parametrize(
    "escape", ["../server", "escape", "absolute_symlink", "absolute_parent"]
)
def test_read_escape_is_refused(trees, escape):
    server, root = trees
    (root / "escape").symlink_to(server, target_is_directory=True)
    if escape == "absolute_symlink":
        escape = str(root / "escape")
    elif escape == "absolute_parent":
        escape = str(root / ".." / "server")
    result = _wrapper("ast_context", ContextTool(), root)(path=escape)
    assert isinstance(result, dict) and result["success"] is False
    assert "escapes" in result["error"]


async def test_concurrent_facade_sessions_keep_independent_roots(trees, monkeypatch):
    import asyncio
    from contextvars import ContextVar
    from typing import cast

    from axm_mcp.facade.catalog import ToolCatalog

    server, first = trees
    second = first.parent / "second"
    second.mkdir()
    active = ContextVar[WriteContract | None]("test_contract", default=None)
    monkeypatch.setattr("axm_mcp.wrapping._HTTP_MODE", True)
    catalog = ToolCatalog(
        {"write_file": cast("ToolEntry", WriteFileTool())},
        shared_mode=True,
        write_contract_resolver=active.get,
    )

    async def write(root: Path) -> object:
        token = active.set(
            WriteContract.from_mapping(
                {"execution_root": str(root), "allowed_prefixes": [str(root)]}
            )
        )
        try:
            return await catalog.acall(
                "write_file", {"path": ".", "file": "x.py", "content": root.name}
            )
        finally:
            active.reset(token)

    await asyncio.gather(write(first), write(second))
    assert (first / "x.py").read_text() == first.name
    assert (second / "x.py").read_text() == second.name
    assert not (server / "x.py").exists()


async def test_async_authorization_and_lock_consume_one_prepared_payload(
    trees, monkeypatch
):
    _, root = trees
    resolutions = []
    lock_paths = []

    def contract():
        resolutions.append(root)
        return WriteContract.from_mapping(
            {"execution_root": str(root), "allowed_prefixes": [str(root)]}
        )

    def tool(path="."):
        return {"path": path}

    def lock(name, kwargs):
        lock_paths.append(kwargs["path"])

    monkeypatch.setattr("axm_mcp.wrapping._HTTP_MODE", True)
    monkeypatch.setattr("axm_mcp.wrapping._select_lock", lock)
    wrapper = build_wrappers(
        "git_preflight", tool, shared_mode=True, write_contract_resolver=contract
    )[1]
    assert await wrapper(path=".") == {"path": str(root)}
    assert await wrapper(path=str(root)) == {"path": str(root)}
    assert lock_paths == [str(root), str(root)]
    assert resolutions == [root, root]


def test_plain_tool_path_default_is_session_local(trees):
    from typing import cast

    _, root = trees

    def tool(*, path: Path = Path(".")) -> dict[str, object]:
        return {"root": str(path)}

    wrapper = _wrapper("ast_context", cast("ToolEntry", tool), root)
    assert wrapper() == {"root": str(root)}
