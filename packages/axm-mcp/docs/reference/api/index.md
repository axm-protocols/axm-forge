# Python API

The package root exports **`main`, `__version__`, and `create_scoped_mcp_app`** through
`axm_mcp.__all__`. This is a server package; use MCP to call its built-ins.

## Version

```python
from axm_mcp import __version__

assert isinstance(__version__, str)
```

The version comes from hatch-vcs-generated `_version.py`. A raw source
checkout needs a package build/install before importing the root;
the generated file is not a manually maintained source file.

## CLI entry point

::: axm_mcp.main

`main()` invokes the lifecycle command parser using process arguments. It
may start a long-lived server or perform service-management actions; it is
not a request/response API to invoke a tool.

## Host-owned scoped MCP

`create_scoped_mcp_app` creates an independent ASGI application for a host-owned
conversation capability. Mount it at a capability-specific prefix: `/mcp` and
adjacent `/health` share the same authorization. The host resolves URL/credentials;
an addon or client header cannot widen the tool list or write contract.

Supply an immutable `allowed_tools` list of logical targets, a validated
`DeclarativeToolManifest` (or `None`), an asynchronous
`invoke(name, arguments) -> ToolResult`, and
`authorize(asgi_scope) -> bool | Awaitable[bool]`. Authorization runs before every
HTTP request and named MCP dispatch, including health. `policy_revision` identifies
the host's immutable policy. Optional `tools` injects existing backend tools;
otherwise the common installed AXM resolver is used. Backend tools require an
explicit host `write_contract`, reuse normal wrappers, validation and locks, and
never inherit an ambient write contract from client headers.

UI schemas are exposed exactly, not reconstructed from Python kwargs. Direct and
facade invocation use the same dispatcher. Search/describe/capabilities reveal only
permitted targets; facade wrappers do not grant access to their underlying full
catalogue. A nonempty scope exposes `axm_search`, `axm_describe`, `axm_call`, and
`axm_capabilities` as transport helpers. Their names are not permission targets and
must not be included in `allowed_tools`. Empty scopes expose no tools and refuse
even facade calls. Nested AXM named dispatch is restricted by the same context.
SDK-resolved handles and cached tool nodes also revalidate the host lease and write
authority immediately before their effect. Backend calls run on workers, preserving
ContextVars and rechecking authorization after any keyed-lock wait. Async host
authorization is scheduled on its owning loop; a synchronous nested SDK call made
directly on that loop is refused for an async policy instead of blocking it. Hosts
must offload such synchronous backend work. A retained handle cannot execute after
its request loop has closed.

Scoped backend responses preserve the structural success/error signal even when a
tool supplies human-readable text. A failed ToolResult is never turned into a
successful MCP string response, through either the direct or facade route.
The success flag must be an actual boolean: strings, integers, lists and missing
structural envelopes are not passing results. UI confirmations have the same
strict boolean requirement.

The returned app is dynamically mountable without starting a manager per capability:
each stateless HTTP request owns and closes its SDK manager lifespan. Revocation
must be checked by the host authorization callback and, for in-flight UI work, by
the host broker. This factory does not own the browser or a target view.

Health returns `kind="axm-scoped-mcp"`, `schema_version=1`, `policy_revision`,
`tool_scope_sha256`, and `write_contracts_enforced`. The digest uses the shared
`axm.tool_scope_sha256` over functional target names only. Health contains no
capability secret. It is a contract with a trusted host endpoint, not cryptographic
attestation of arbitrary URLs. Expired/revoked/unauthenticated capabilities return
HTTP 403, including health.

::: axm_mcp.create_scoped_mcp_app

## Other implementation seams

The following are useful when embedding/testing this implementation, but are
**not exported at the package root**. Their signatures and lifecycles should
be reviewed against the installed version before integration.

| Import | Contract / caution |
|---|---|
| `axm_mcp.discovery.discover_tools` | Instantiate installed entry points; loading can execute plugin initialization |
| `axm_mcp.facade.ToolCatalog` | Index a supplied entry map; `call` returns text synchronously, `acall` uses the async wrapper |
| `axm_mcp.mcp_app.build_http_app` | Build the registered MCPServer ASGI application; importing the module already discovers tools |
| `axm_mcp.server.serve` | Run HTTP; unlike CLI, a missing port can use the environment. Records `shared`/`dedicated` for `/health`'s `serve_mode` and `write_contracts_enforced` |
| `axm_mcp.verify.verify_project` | Aggregate using a supplied provider mapping; no global pass boolean |
| `axm_mcp.web_fetch.fetch_page` | Async optional-backend fetch; result is a dictionary |
| `axm_mcp.session_contracts.SessionContractRegistry` | In-memory bind/resolve/release/explicit purge; expiry is not automatic |
| `axm_mcp.server.SharedModeNotArmedError` | Lower-level shared serving requested without a resolver |
| `axm_mcp.session_contracts.UnboundSessionError` | Missing session identity or contract |
| `axm_mcp.session_contracts.WriteContractHeaderError` | Invalid strict contract-header payload |
| `axm_mcp.facade.catalog.UnknownToolError` | A requested name is not in the supplied catalog |

The lifecycle and HTTP middleware require their own setup; importing
`build_http_app` is not equivalent to executing the CLI's shared startup.
Prefer the supported [CLI](../cli.md) for launching the server.
