# Facade and result contracts

## Listing and dispatch

With the facade enabled, MCP `tools/list` includes four facade meta-tools,
the discovered tools that opt into `expose_directly`, and the built-ins
`verify`, `web_fetch`, `list_tools`. All successfully discovered entries
and the first two built-ins participate in the callable catalog.

| MCP tool | Parameters | Result |
|---|---|---|
| `axm_search` | `query=""`, `domain=null`, `limit=20` | Text listing matching names, summaries and metadata |
| `axm_describe` | required `name` | Text contract with typed parameters/defaults, or unknown-tool diagnostic |
| `axm_call` | required `name`, `arguments=null` | Tool text or rendered result/error |
| `axm_capabilities` | `domain=null` | Text grouping names by domain |
| `list_tools` | `kwargs={}` with the MCP 1.30 generated schema | Text enumeration of discovered entries and registered meta-tools |

`list_tools`' Python body takes `**kwargs` and ignores them, but MCP 1.30
publishes `kwargs` as a required object field. Call it with
`arguments={"kwargs": {}}`; an empty arguments object fails validation in
that environment.

These are text responses, **not JSON objects matching the internal catalog
methods' return types**. `list_tools` and facade meta-tools themselves are
not callable catalog entries; call them directly.

Search is a case-insensitive **substring** match against name, first-line
summary, tags and domain, returned in name order, not relevance order.
`domain` is an exact match. An empty query browses entries up to `limit`.
Use a positive limit: zero/negative values are not validated and may still
return the first match. There is no pagination cursor. Use `list_tools`
for an inventory.

## Call sequence

The following are MCP `tools/call` parameter objects, sent individually by
your client (not whole JSON-RPC requests):

```json
{"name": "axm_search", "arguments": {"query": "ast", "limit": 20}}
```

```json
{"name": "axm_describe", "arguments": {"name": "ast_context"}}
```

```json
{"name": "axm_call", "arguments": {"name": "ast_context", "arguments": {"path": "/absolute/path/to/package", "depth": 1}}}
```

The example requires axm-ast installed in the server environment. A tool
absent from the client's direct list may still be reachable through the
facade. A tool absent from the catalog may be uninstalled, disabled, or have
failed during loading; inspect server logs and restart after fixing it.

## ToolResult at the MCP boundary

| Tool outcome | Direct wrapper / facade rendering |
|---|---|
| Success with string `text` (including empty string) | That string, without the structured `data` |
| Failure with nonempty `text` | Diagnostic text with error marker/prefix when the first line does not already contain the error; hint appended if needed |
| Result without usable text | Data fields plus `success`, optional `error` and `hint` |
| Exception in tool execution | `success=False` and exception diagnostic |
| Facade unknown tool | Text beginning `error:` |
| Facade missing/unexpected argument | Text diagnostic and accepted-parameter hint |
| Facade invalid annotated value | Pydantic validation surfaced as an MCP ToolError |

The facade renders dictionary results as `key: value` lines, not JSON.
Do not parse that human-readable output as a stable data API. Direct Python
AXMTool callers receive the original ToolResult; a text response through MCP
does not also preserve its structured data.

Reserved data keys `success`, `error`, `hint` move to `data_success`,
`data_error`, `data_hint` on the dictionary path. Avoid **both** sets of
names in data: an existing destination key can be overwritten by relocation.

Argument binding follows the callable's signature. A tool accepting
`**kwargs` can accept unknown keys without complaint, and may ignore them.
Read its contract before mutations. Annotated inputs may be coerced by
Pydantic; this is not strict JSON-type identity validation.

## Discovery boundaries

Entry points use the group `axm.tools`. Classes are instantiated without
arguments; plain callables are retained. Loading exceptions are logged and
that entry is skipped. The entry-point name is the registry key. Duplicate
names overwrite earlier entries in discovery order; do not rely on that
ordering or collide with built-ins/meta-tools.

Changing files without installing package metadata does not add an entry
point. Install into the **server's environment** and restart it. A uvx-managed
server does not discover packages installed into an unrelated project venv.
