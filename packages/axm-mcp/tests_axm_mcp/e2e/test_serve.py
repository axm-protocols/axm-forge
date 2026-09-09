"""E2E: a second ``axm-mcp serve`` is refused while the first daemon is alive."""

from __future__ import annotations

import asyncio
import json
import subprocess
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


@pytest.mark.e2e
def test_serve(
    tmp_path: Path,
    cli_binary: str,
    free_port: int,
    sandbox_env: Callable[[Path], dict[str, str]],
    serve_daemon: Callable[[Path, int], subprocess.Popen[str]],
) -> None:
    """Double-start guard: the second ``serve`` exits non-zero, PID file intact.

    Drives the PID-file lifecycle end-to-end over subprocess with real exit
    codes: a live daemon owns the sandboxed PID file, and a second ``serve``
    against the same ``$HOME`` must refuse rather than clobber the survivor.
    """
    first = serve_daemon(tmp_path, free_port)
    pid_file = tmp_path / ".axm" / "mcp-server.pid"
    assert pid_file.read_text().strip() == str(first.pid)

    second = subprocess.run(  # noqa: S603
        [cli_binary, "serve", "--host", "127.0.0.1", "--port", str(free_port)],
        capture_output=True,
        text=True,
        env=sandbox_env(tmp_path),
        timeout=30,
        check=False,
    )

    assert second.returncode != 0
    assert "already running" in second.stderr.lower()
    # The survivor's PID file is untouched -- still points at the first daemon.
    assert pid_file.read_text().strip() == str(first.pid)
    assert first.poll() is None


@pytest.mark.e2e
def test_shared_stdio_is_refused(
    tmp_path: Path,
    cli_binary: str,
    sandbox_env: Callable[[Path], dict[str, str]],
) -> None:
    """AC5: stdio cannot arm shared mode without a session identity."""
    result = subprocess.run(  # noqa: S603
        [cli_binary, "serve", "--shared"],
        capture_output=True,
        text=True,
        env=sandbox_env(tmp_path),
        timeout=10,
        check=False,
    )

    assert result.returncode == 1
    assert "shared mode" in result.stderr.lower()


@pytest.mark.e2e
def test_invalid_configured_serve_mode_is_refused(
    tmp_path: Path,
    cli_binary: str,
    sandbox_env: Callable[[Path], dict[str, str]],
) -> None:
    """AC6: serve exits 1 and names an invalid environment-configured mode."""
    env = sandbox_env(tmp_path)
    env["AXM_MCP_SERVE_MODE"] = "bogus"

    result = subprocess.run(  # noqa: S603
        [cli_binary, "serve"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
        check=False,
    )

    assert result.returncode == 1
    assert "bogus" in result.stderr.lower()
    assert "invalid" in result.stderr.lower()
    assert "serve mode" in result.stderr.lower()


def _shared_mode_process(
    tmp_path: Path,
    cli_binary: str,
    free_port: int,
    sandbox_env: Callable[[Path], dict[str, str]],
) -> tuple[subprocess.Popen[str], dict[str, str], Path]:
    """Start a shared-mode server with configuration isolated under tmp_path."""
    config_home = tmp_path / ".axm"
    config_home.mkdir(parents=True, exist_ok=True)
    (config_home / "config.toml").write_text(
        '[mcp]\nserve_mode = "shared"\n',
        encoding="utf-8",
    )
    env = sandbox_env(tmp_path)
    env["AXM_HOME"] = str(config_home)
    env.pop("AXM_MCP_SERVE_MODE", None)
    stderr_path = tmp_path / "shared-serve.stderr"
    stderr_stream = stderr_path.open("w", encoding="utf-8")
    process = subprocess.Popen(  # noqa: S603
        [cli_binary, "serve", "--host", "127.0.0.1", "--port", str(free_port)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=stderr_stream,
        text=True,
        env=env,
    )
    stderr_stream.close()
    return process, env, stderr_path


def _wait_for_status(
    cli_binary: str,
    free_port: int,
    env: dict[str, str],
    process: subprocess.Popen[str],
) -> subprocess.CompletedProcess[str]:
    """Poll the public status command until the server responds or serve exits."""
    deadline = time.monotonic() + 10
    while True:
        result = subprocess.run(  # noqa: S603
            [
                cli_binary,
                "status",
                "--host",
                "127.0.0.1",
                "--port",
                str(free_port),
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 or process.poll() is not None:
            return result
        if time.monotonic() >= deadline:
            return result
        time.sleep(0.05)


def _stop_server(
    cli_binary: str,
    env: dict[str, str],
    process: subprocess.Popen[str],
) -> None:
    """Stop through the public CLI, with a subprocess fallback for failed starts."""
    subprocess.run(  # noqa: S603
        [cli_binary, "stop"],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
        check=False,
    )
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _write_contract_header(scope: Path) -> str:
    """Render the transport header used by one shared-server session."""
    return json.dumps(
        {
            "execution_root": str(scope),
            "allowed_prefixes": [str(scope)],
            "markdown_only_prefixes": [],
        }
    )


def _tool_decision(result: Any) -> tuple[bool, str]:
    """Extract the ToolResult decision from an MCP CallToolResult."""
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict) and "success" in structured:
        return bool(structured["success"]), str(structured.get("error", ""))
    rendered = "\n".join(
        str(block.text)
        for block in result.content
        if getattr(block, "type", None) == "text"
    )
    try:
        payload = json.loads(rendered)
    except json.JSONDecodeError:
        fields = {
            key: value
            for line in rendered.splitlines()
            if ": " in line
            for key, value in [line.split(": ", 1)]
        }
        if "success" in fields:
            return fields["success"].casefold() == "true", fields.get("error", "")
        return not bool(getattr(result, "isError", False)), rendered
    if isinstance(payload, dict) and "success" in payload:
        return bool(payload["success"]), str(payload.get("error", ""))
    return not bool(getattr(result, "isError", False)), rendered


@asynccontextmanager
async def _session_transport(url: str, headers: dict[str, str]):
    """Own the configured HTTP client for one MCP transport session.

    mcp 2.x yields ``(read, write)`` only -- the third ``get_session_id``
    element was dropped. The identity still travels as the ``mcp-session-id``
    response header, so an event hook captures it and this helper keeps
    yielding a 3-tuple, preserving what the isolation tests assert on.
    """
    seen: dict[str, str] = {}

    async def _capture(response: httpx.Response) -> None:
        sid = response.headers.get("mcp-session-id")
        if sid is not None:
            seen["id"] = sid

    async with httpx.AsyncClient(
        headers=headers, event_hooks={"response": [_capture]}
    ) as http_client:
        async with streamable_http_client(url, http_client=http_client) as streams:
            read_stream, write_stream = streams
            yield read_stream, write_stream, lambda: seen.get("id")


async def _call_shared_tool(
    free_port: int,
    *,
    headers: dict[str, str],
    name: str,
    arguments: dict[str, object],
) -> tuple[bool, str, str]:
    """Open one real streamable-HTTP session and call one MCP tool."""
    url = f"http://127.0.0.1:{free_port}/mcp"
    async with _session_transport(url, headers) as streams:
        read_stream, write_stream, get_session_id = streams
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)
            session_id = get_session_id()
    assert session_id is not None
    success, error = _tool_decision(result)
    return success, error, session_id


async def _call_direct_across_sessions(
    free_port: int,
    scope_a: Path,
    scope_b: Path,
) -> tuple[tuple[bool, str], tuple[bool, str]]:
    """Keep B alive while A writes once locally and once across its boundary."""
    url = f"http://127.0.0.1:{free_port}/mcp"
    headers_b = {"X-AXM-Write-Contract": _write_contract_header(scope_b)}
    headers_a = {"X-AXM-Write-Contract": _write_contract_header(scope_a)}
    async with _session_transport(url, headers_b) as streams_b:
        read_b, write_b, _get_b_session_id = streams_b
        async with ClientSession(read_b, write_b) as session_b:
            await session_b.initialize()
            await session_b.list_tools()
            async with _session_transport(url, headers_a) as streams_a:
                read_a, write_a, _get_a_session_id = streams_a
                async with ClientSession(read_a, write_a) as session_a:
                    await session_a.initialize()
                    own = await session_a.call_tool(
                        "batch_edit",
                        {
                            "path": str(scope_a),
                            "operations": [
                                {
                                    "op": "create",
                                    "file": "own-control.txt",
                                    "content": "owned by A",
                                }
                            ],
                        },
                    )
                    cross = await session_a.call_tool(
                        "batch_edit",
                        {
                            "path": str(scope_b),
                            "operations": [
                                {
                                    "op": "create",
                                    "file": "blocked.txt",
                                    "content": "must not land",
                                }
                            ],
                        },
                    )
    return _tool_decision(own), _tool_decision(cross)


def _start_ready_shared(
    tmp_path: Path,
    cli_binary: str,
    free_port: int,
    sandbox_env: Callable[[Path], dict[str, str]],
) -> tuple[subprocess.Popen[str], dict[str, str]]:
    """Start a shared server and require its public status probe to pass."""
    process, env, stderr_path = _shared_mode_process(
        tmp_path,
        cli_binary,
        free_port,
        sandbox_env,
    )
    status = _wait_for_status(cli_binary, free_port, env, process)
    assert status.returncode == 0, stderr_path.read_text(encoding="utf-8")
    return process, env


@pytest.mark.e2e
def test_shared_direct_batch_edit_writes_within_declared_scope(
    tmp_path: Path,
    cli_binary: str,
    free_port: int,
    sandbox_env: Callable[[Path], dict[str, str]],
) -> None:
    """AC2: a direct tool writes inside its session's declared perimeter."""
    scope = tmp_path / "direct-own"
    scope.mkdir()
    process, env = _start_ready_shared(tmp_path, cli_binary, free_port, sandbox_env)
    try:
        success, error, _session_id = asyncio.run(
            _call_shared_tool(
                free_port,
                headers={"X-AXM-Write-Contract": _write_contract_header(scope)},
                name="batch_edit",
                arguments={
                    "path": str(scope),
                    "operations": [
                        {
                            "op": "create",
                            "file": "direct.txt",
                            "content": "direct content",
                        }
                    ],
                },
            )
        )
        assert success, error
        assert (scope / "direct.txt").read_text() == "direct content"
    finally:
        _stop_server(cli_binary, env, process)


@pytest.mark.e2e
def test_shared_direct_batch_edit_rejects_other_session_scope(
    tmp_path: Path,
    cli_binary: str,
    free_port: int,
    sandbox_env: Callable[[Path], dict[str, str]],
) -> None:
    """AC2: session A cannot write inside session B's declared perimeter."""
    scope_a = tmp_path / "session-a"
    scope_b = tmp_path / "session-b"
    scope_a.mkdir()
    scope_b.mkdir()
    process, env = _start_ready_shared(tmp_path, cli_binary, free_port, sandbox_env)
    try:
        own, cross = asyncio.run(
            _call_direct_across_sessions(free_port, scope_a, scope_b)
        )
        assert own[0], own[1]
        assert (scope_a / "own-control.txt").read_text() == "owned by A"
        assert not cross[0]
        assert not (scope_b / "blocked.txt").exists()
    finally:
        _stop_server(cli_binary, env, process)


@pytest.mark.e2e
def test_shared_facade_write_file_writes_within_declared_scope(
    tmp_path: Path,
    cli_binary: str,
    free_port: int,
    sandbox_env: Callable[[Path], dict[str, str]],
) -> None:
    """AC3: axm_call writes inside its session's declared perimeter."""
    scope = tmp_path / "facade-own"
    scope.mkdir()
    process, env = _start_ready_shared(tmp_path, cli_binary, free_port, sandbox_env)
    try:
        success, error, _session_id = asyncio.run(
            _call_shared_tool(
                free_port,
                headers={"X-AXM-Write-Contract": _write_contract_header(scope)},
                name="axm_call",
                arguments={
                    "name": "write_file",
                    "arguments": {
                        "path": str(scope),
                        "file": "facade.txt",
                        "content": "facade content",
                    },
                },
            )
        )
        assert success, error
        assert (scope / "facade.txt").read_text() == "facade content"
    finally:
        _stop_server(cli_binary, env, process)


@pytest.mark.e2e
def test_shared_facade_write_file_rejects_unbound_session(
    tmp_path: Path,
    cli_binary: str,
    free_port: int,
    sandbox_env: Callable[[Path], dict[str, str]],
) -> None:
    """AC3: axm_call refuses and names a session with no declared perimeter."""
    declared_scope = tmp_path / "declared"
    unbound_scope = tmp_path / "unbound"
    declared_scope.mkdir()
    unbound_scope.mkdir()
    process, env = _start_ready_shared(tmp_path, cli_binary, free_port, sandbox_env)
    try:
        declared_success, declared_error, _declared_id = asyncio.run(
            _call_shared_tool(
                free_port,
                headers={
                    "X-AXM-Write-Contract": _write_contract_header(declared_scope)
                },
                name="axm_call",
                arguments={
                    "name": "write_file",
                    "arguments": {
                        "path": str(declared_scope),
                        "file": "control.txt",
                        "content": "declared control",
                    },
                },
            )
        )
        success, error, session_id = asyncio.run(
            _call_shared_tool(
                free_port,
                headers={},
                name="axm_call",
                arguments={
                    "name": "write_file",
                    "arguments": {
                        "path": str(unbound_scope),
                        "file": "blocked.txt",
                        "content": "must not land",
                    },
                },
            )
        )
        assert declared_success, declared_error
        assert (declared_scope / "control.txt").read_text() == "declared control"
        assert not success
        assert session_id in error
        assert not (unbound_scope / "blocked.txt").exists()
    finally:
        _stop_server(cli_binary, env, process)


@pytest.mark.e2e
def test_shared_config_serve_is_reported_running(
    tmp_path: Path,
    cli_binary: str,
    free_port: int,
    sandbox_env: Callable[[Path], dict[str, str]],
) -> None:
    """AC1: configured shared serve starts and status reports it running."""
    process, env, _stderr_path = _shared_mode_process(
        tmp_path,
        cli_binary,
        free_port,
        sandbox_env,
    )
    try:
        status_result = _wait_for_status(cli_binary, free_port, env, process)
        assert status_result.returncode == 0
        assert "server running" in status_result.stdout.lower()
    finally:
        _stop_server(cli_binary, env, process)


@pytest.mark.e2e
def test_shared_config_serve_emits_no_arming_or_stdio_refusal(
    tmp_path: Path,
    cli_binary: str,
    free_port: int,
    sandbox_env: Callable[[Path], dict[str, str]],
) -> None:
    """AC2: configured shared serve emits neither shared-mode refusal."""
    process, env, stderr_path = _shared_mode_process(
        tmp_path,
        cli_binary,
        free_port,
        sandbox_env,
    )
    try:
        _wait_for_status(cli_binary, free_port, env, process)
        stderr = stderr_path.read_text(encoding="utf-8").lower()
        normalized_stderr = stderr.replace("-", " ")
        assert process.poll() is None, stderr
        assert "sharedmodenotarmederror" not in stderr
        assert "session identity" not in normalized_stderr
        assert not ("stdio" in stderr and "shared mode" in stderr)
    finally:
        _stop_server(cli_binary, env, process)
