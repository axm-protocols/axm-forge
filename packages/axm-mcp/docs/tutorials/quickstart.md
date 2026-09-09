# Quick Start

Connect one server, inspect its catalog, and make a read-only call.

## Prerequisites

Use Python 3.12 or later, uv, and an MCP client supporting stdio.
The server and the packages providing your tools must be installed in the
**same Python environment**.

## Step 1: Choose the tool set

For the Forge developer tools, use this command and argument vector in your
MCP client's stdio-server configuration:

```json
{
  "command": "uvx",
  "args": ["--python", "3.12", "--from", "axm-mcp[forge]", "axm-mcp"]
}
```

This is a server process definition; the enclosing configuration keys and
scope depend on your client. Save it through that client's supported
configuration flow and reconnect. Keep stdout reserved for MCP traffic.

The base package registers `verify`, `web_fetch`, `list_tools` and the
facade, but does not install the optional implementations they may need.

| Extra | Adds |
|---|---|
| `forge` | axm-ast, axm-audit, axm-init, axm-git, axm-anvil, axm-edit, axm-smelt |
| `all` | forge plus axm-bib and axm-ticket |
| `ast`, `audit`, `init`, `git`, `anvil`, `edit`, `smelt`, `bib`, `ticket` | The corresponding individual package |
| `web` | Scrapling dependency; see [web fetching](../reference/builtins.md#web_fetch) for fetcher requirements |

`all` does not include `web`, every AXM package, or every possible tool.
Use a pinned package version when you need a repeatable server environment.
The unpinned example follows dependency resolution, not the code in a local
checkout.

## Step 2: Inspect the connection

Send this MCP `tools/call` parameter object through your client:

```json
{"name": "list_tools", "arguments": {"kwargs": {}}}
```

The empty `kwargs` field accommodates the schema emitted for this tool by
MCP 1.30: omitting it yields a missing-field error. The text lists the
installed, successfully loaded tool entries and the
server's meta-tools. It differs from the protocol's direct `tools/list`:
a small direct list is normal with the facade enabled.

Find a code-analysis tool:

```json
{"name": "axm_search", "arguments": {"query": "ast_context"}}
```

Then request its contract:

```json
{"name": "axm_describe", "arguments": {"name": "ast_context"}}
```

If it is absent, check the server environment, `AXM_DISABLE_TOOLS` and
startup logs. Reinstalling an unrelated project environment will not fix a
uvx server's catalog.

## Step 3: Make a read-only call

Replace the path with an existing local package:

```json
{"name": "axm_call", "arguments": {"name": "ast_context", "arguments": {"path": "/absolute/path/to/package", "depth": 1}}}
```

You should receive a module/package overview. This proves dispatch as well as
connection and discovery. Use absolute paths: the server process has one
working directory, which may differ from the client project's directory.

## Step 4: Interpret a quality check

If you installed the `forge` extra:

```json
{"name": "verify", "arguments": {"path": "/absolute/path/to/package"}}
```

Read the audit and governance sections; skipped dependencies, failing rules
and tool errors must be considered separately. The outer ToolResult success
does not certify a quality pass. [Verify a project](../howto/verify.md)
explains that distinction and the command's side effects.

## Next steps

- [Add your own tool](../howto/add-tool.md).
- [Run a persistent HTTP server](../howto/migration-http.md).
- [Inspect facade and error contracts](../reference/facade.md).
