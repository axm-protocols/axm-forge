"""Host-owned, isolated MCP applications with positive tool permissions."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Awaitable, Callable, Mapping
from contextvars import ContextVar
from typing import cast

from axm import (
    DeclarativeToolManifest,
    ToolResult,
    tool_access_scope,
    tool_scope_sha256,
)
from axm.tools.access import tool_execution_guard
from axm.tools.base import AXMTool
from axm.tools.declarative import DeclarativeTool, DeclarativeToolDefinition
from axm.tools.dependency_reads import dependency_read_context
from axm.tools.write_scope import WriteContract
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from mcp.server import Server, ServerRequestContext
from mcp.server.mcpserver import MCPServer
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
)
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from axm_mcp.discovery import ToolEntry, discover_tools, register_tools
from axm_mcp.facade.catalog import ToolCatalog
from axm_mcp.session_paths import path_defaults
from axm_mcp.wrapping import _WrapperCtx, _write_refusal, build_wrappers

__all__ = ["create_scoped_mcp_app"]

type _Invoke = Callable[[str, dict[str, object]], Awaitable[ToolResult]]
type _Authorize = Callable[[Scope], bool | Awaitable[bool]]
_REQUEST: ContextVar[Scope | None] = ContextVar("axm_scoped_request", default=None)
_FACADE = frozenset({"axm_search", "axm_describe", "axm_call", "axm_capabilities"})


async def _authorized(authorize: _Authorize, scope: Scope | None) -> bool:
    if scope is None:
        return False
    result = authorize(scope)
    return bool(await result) if inspect.isawaitable(result) else bool(result)


def _authorize_on_loop(authorize: _Authorize, scope: Scope | None) -> bool:
    authorized = authorize(scope) if scope is not None else False
    if inspect.isawaitable(authorized):
        if inspect.iscoroutine(authorized):
            authorized.close()
        raise PermissionError("async scoped dispatch requires a worker thread")
    return bool(authorized)


def _authorize_execution(
    authorize: _Authorize, scope: Scope | None, loop: asyncio.AbstractEventLoop
) -> None:
    if not loop.is_running() or loop.is_closed():
        raise PermissionError("scope unavailable")
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is loop:
        authorized = _authorize_on_loop(authorize, scope)
    else:
        future = asyncio.run_coroutine_threadsafe(_authorized(authorize, scope), loop)
        try:
            authorized = future.result(timeout=30)
        except BaseException:
            future.cancel()
            raise
    if not authorized:
        raise PermissionError("scope unavailable")


def _result(result: ToolResult, *, ui: bool = False) -> CallToolResult:
    if not isinstance(result.success, bool):
        result = ToolResult(
            success=False, error="malformed ToolResult: success must be a boolean"
        )
    data = (
        result.data
        if result.success and ui
        else {
            "success": result.success,
            "data": result.data,
            **({"error": result.error} if result.error else {}),
        }
    )
    return CallToolResult(
        content=[TextContent(type="text", text=result.text or json.dumps(data))],
        structured_content=data,
        is_error=not result.success,
    )


def _facade_tools() -> list[Tool]:
    def schema(properties: dict[str, object], required: list[str]) -> dict[str, object]:
        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }

    return [
        Tool(
            name="axm_search",
            description="Search permitted AXM tools.",
            input_schema=schema({"query": {"type": "string"}}, []),
        ),
        Tool(
            name="axm_describe",
            description="Describe one permitted AXM tool.",
            input_schema=schema({"name": {"type": "string"}}, ["name"]),
        ),
        Tool(
            name="axm_call",
            description="Call one permitted AXM tool.",
            input_schema=schema(
                {"name": {"type": "string"}, "arguments": {"type": "object"}}, ["name"]
            ),
        ),
        Tool(
            name="axm_capabilities",
            description="List permitted AXM tool names.",
            input_schema=schema({}, []),
        ),
    ]


class _ScopedCatalog:
    def __init__(
        self,
        allowed: frozenset[str],
        definitions: Mapping[str, DeclarativeToolDefinition],
        business: dict[str, ToolEntry],
        invoke: _Invoke,
        contract: WriteContract | None,
    ) -> None:
        self.allowed = allowed
        self.definitions = dict(definitions)
        self.invoke = invoke
        self.contract = contract
        self.business = ToolCatalog(
            business,
            shared_mode=True,
            write_contract_resolver=lambda: contract,
        )
        self.wrappers = {
            name: build_wrappers(
                name,
                tool,
                shared_mode=True,
                write_contract_resolver=lambda: contract,
                preserve_result=True,
            )[1]
            for name, tool in business.items()
        }
        self.schema_server = MCPServer("AXM scoped schema")
        register_tools(
            self.schema_server,
            business,
            shared_mode=True,
            write_contract_resolver=lambda: contract,
        )

    async def tools(self) -> list[Tool]:
        return [
            *await self.schema_server.list_tools(),
            *(
                Tool(
                    name=definition.name,
                    description=definition.description,
                    input_schema=definition.input_schema,
                    output_schema=definition.output_schema,
                )
                for definition in self.definitions.values()
            ),
        ]

    async def describe(self, name: str) -> dict[str, object]:
        if name not in self.allowed:
            raise PermissionError(f"undeclared tool refused: {name}")
        definition = self.definitions.get(name)
        if definition is not None:
            return {
                "name": name,
                "description": definition.description,
                "inputSchema": definition.input_schema,
                "outputSchema": definition.output_schema,
                "execution": "ui",
            }
        return self.business.describe(name)

    async def call(self, name: str, arguments: dict[str, object]) -> CallToolResult:
        if name not in self.allowed:
            return _result(
                ToolResult(success=False, error=f"undeclared tool refused: {name}")
            )
        definition = self.definitions.get(name)
        if definition is not None:
            definition.validate_input(arguments)
            result = await self.invoke(name, arguments)
            return _result(definition.validate_result(result), ui=True)
        tool = self.business._get(name)
        arguments = self.business._bind_check(tool, arguments, name)
        wrapped = await self.wrappers[name](**arguments)
        if isinstance(wrapped, str) or not isinstance(wrapped.get("success"), bool):
            return _result(
                ToolResult(
                    success=False,
                    error="malformed backend result: success must be a boolean",
                )
            )
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(wrapped))],
            structured_content=wrapped,
            is_error=wrapped.get("success") is False,
        )

    async def facade(self, name: str, args: dict[str, object]) -> CallToolResult:
        schemas = {tool.name: tool.input_schema for tool in _facade_tools()}

        Draft202012Validator(schemas[name]).validate(args)
        if name == "axm_call":
            return await self.call(
                cast(str, args["name"]),
                cast(dict[str, object], args.get("arguments", {})),
            )
        if name == "axm_describe":
            data: object = await self.describe(cast(str, args["name"]))
        elif name == "axm_search":
            query = cast(str, args.get("query", "")).casefold()
            data = [
                {"name": tool.name, "description": tool.description}
                for tool in await self.tools()
                if query in f"{tool.name} {tool.description}".casefold()
            ]
        else:
            data = sorted(self.allowed)
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(data))])


class _ScopedApp:
    """Stateless ASGI mount; no globally running session manager to reconfigure."""

    def __init__(
        self,
        server: Server[object],
        authorize: _Authorize,
        health: dict[str, object],
    ) -> None:
        self.server = server
        self.authorize = authorize
        self.health = health

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            # Each stateless HTTP request owns its SDK manager lifespan.
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        if scope["type"] != "http":
            await JSONResponse({"error": "unsupported transport"}, status_code=400)(
                scope, receive, send
            )
            return
        if not await _authorized(self.authorize, scope):
            await JSONResponse({"error": "scope unavailable"}, status_code=403)(
                scope, receive, send
            )
            return
        if scope["path"].removeprefix(scope.get("root_path", "")) == "/health":
            await JSONResponse(self.health)(scope, receive, send)
            return
        token = _REQUEST.set(scope)
        try:
            app = self.server.streamable_http_app(
                stateless_http=True, json_response=True
            )
            async with app.router.lifespan_context(app):
                await app(scope, receive, send)
        finally:
            _REQUEST.reset(token)


def _manifest_definitions(
    manifest: DeclarativeToolManifest | None,
    source: Mapping[str, ToolEntry],
) -> dict[str, DeclarativeToolDefinition]:
    definitions = {tool.name: tool for tool in manifest.tools} if manifest else {}
    for name, definition in definitions.items():
        existing = source.get(name)
        if existing is not None and (
            not isinstance(existing, DeclarativeTool)
            or existing.definition != definition
        ):
            raise ValueError(f"UI/Python tool collision: {name}")
    return definitions


def _backend_entries(
    allowed: frozenset[str],
    definitions: Mapping[str, DeclarativeToolDefinition],
    source: Mapping[str, ToolEntry],
    contract: WriteContract | None,
) -> dict[str, ToolEntry]:
    business = {
        name: tool
        for name, tool in source.items()
        if name in allowed and name not in definitions
    }
    if business and contract is None:
        raise ValueError("host write contract required for backend tools")
    return business


def _resolved_catalog(
    allowed: frozenset[str],
    manifest: DeclarativeToolManifest | None,
    source: dict[str, ToolEntry],
    invoke: _Invoke,
    contract: WriteContract | None,
) -> _ScopedCatalog:
    definitions = _manifest_definitions(manifest, source)
    unknown = allowed - source.keys() - definitions.keys()
    if unknown:
        raise ValueError(f"unknown declared tools: {sorted(unknown)}")
    business = _backend_entries(allowed, definitions, source, contract)
    selected = {name: tool for name, tool in definitions.items() if name in allowed}
    return _ScopedCatalog(allowed, selected, business, invoke, contract)


class _ScopedHandlers:
    def __init__(self, catalog: _ScopedCatalog, authorize: _Authorize) -> None:
        self.catalog = catalog
        self.authorize = authorize

    def execution_guard(self) -> Callable[[str, dict[str, object], object], None]:
        """Bind the request's authority; workers revalidate after lock waits too."""
        loop = asyncio.get_running_loop()
        scope = _REQUEST.get()

        def guard(name: str, arguments: dict[str, object], execute: object) -> None:
            _authorize_execution(self.authorize, scope, loop)
            ctx = _WrapperCtx(
                name=name,
                should_trace=False,
                write_contract_resolver=lambda: self.catalog.contract,
                shared_mode=True,
                path_defaults=path_defaults(execute),
            )
            refusal = _write_refusal(ctx, arguments)
            if refusal is not None:
                raise PermissionError(str(refusal["error"]))

        return guard

    async def list_tools(  # type: ignore[explicit-any]
        self,
        ctx: ServerRequestContext[object],
        params: PaginatedRequestParams | None,
    ) -> ListToolsResult:
        if (
            not await _authorized(self.authorize, _REQUEST.get())
            or not self.catalog.allowed
        ):
            return ListToolsResult(tools=[])
        with tool_access_scope(self.catalog.allowed):
            return ListToolsResult(
                tools=[*await self.catalog.tools(), *_facade_tools()]
            )

    async def call_tool(  # type: ignore[explicit-any]
        self,
        ctx: ServerRequestContext[object],
        params: CallToolRequestParams,
    ) -> CallToolResult:
        if not await _authorized(self.authorize, _REQUEST.get()):
            return _result(ToolResult(success=False, error="scope unavailable"))
        if not self.catalog.allowed:
            return _result(ToolResult(success=False, error="empty tool scope"))
        try:
            with (
                tool_access_scope(self.catalog.allowed),
                tool_execution_guard(self.execution_guard()),
                dependency_read_context(self.catalog.contract),
            ):
                args = cast(dict[str, object], params.arguments or {})
                if params.name in _FACADE:
                    return await self.catalog.facade(params.name, args)
                return await self.catalog.call(params.name, args)
        except (ValidationError, ValueError, TypeError, PermissionError) as exc:
            return _result(ToolResult(success=False, error=str(exc)))


def create_scoped_mcp_app(  # noqa: PLR0913 -- explicit host-owned binding contract
    *,
    allowed_tools: frozenset[str],
    manifest: DeclarativeToolManifest | None,
    invoke: Callable[[str, dict[str, object]], Awaitable[ToolResult]],
    authorize: Callable[[Scope], bool | Awaitable[bool]],
    policy_revision: str,
    tools: Mapping[str, AXMTool] | None = None,
    write_contract: WriteContract | None = None,
) -> ASGIApp:
    """Build a host-owned scope, without modifying the shared MCP server.

    Mount at a capability-specific prefix: /mcp and adjacent /health. The
    authorization callback receives the actual ASGI scope and runs before every
    HTTP request and tool dispatch. Client headers never supply or enlarge tools
    or the write contract. A stateless request owns and closes its SDK manager;
    dynamic mounts therefore need no per-capability startup coordination.
    """
    if not policy_revision or not isinstance(allowed_tools, frozenset):
        raise ValueError("immutable positive tool list and policy revision required")
    if allowed_tools & _FACADE:
        raise ValueError("declare target names, not facade wrappers")
    source = (
        discover_tools() if tools is None else cast(dict[str, ToolEntry], dict(tools))
    )
    catalog = _resolved_catalog(allowed_tools, manifest, source, invoke, write_contract)
    handlers = _ScopedHandlers(catalog, authorize)
    server: Server[object] = Server(
        "AXM scoped MCP",
        on_list_tools=handlers.list_tools,
        on_call_tool=handlers.call_tool,
    )
    return _ScopedApp(
        server,
        authorize,
        {
            "kind": "axm-scoped-mcp",
            "schema_version": 1,
            "policy_revision": policy_revision,
            "tool_scope_sha256": tool_scope_sha256(allowed_tools),
            "write_contracts_enforced": write_contract is not None,
        },
    )
