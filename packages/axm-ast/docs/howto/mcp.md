# Use via MCP

Install `axm-ast` and `axm-mcp` in the environment running the MCP server.
Analysis tools are registered in the `axm.tools` entry-point group.
The dedicated `axm-ast` CLI is also distributed, but its defaults and JSON
shapes are not identical to the tools.

## Discover the invocation contract

Use `axm_search(query="ast_")` or `list_tools()` to inspect the installed
catalog, then `axm_describe(name="ast_inspect")` for argument types and defaults.
Only selected tools appear directly in façade-mode MCP servers. An absent direct
tool is still callable through `axm_call`:

```json
{
  "name": "ast_inspect",
  "arguments": {
    "path": "packages/axm-ast",
    "symbols": ["analyze_package", "search_symbols"],
    "source": true
  }
}
```

Pass this object to `axm_call` from the workspace root, or use an absolute
package path. Do not pass dedicated CLI spellings such as `trace`, `--source`,
or comma-separated module filters as tool arguments. Several tools accept
`**kwargs` and may silently ignore unknown names; successful execution does
not prove that a misspelled option took effect.

## A focused exploration

1. `ast_context(path=..., depth=1)` establishes package structure.
2. `ast_search(path=..., name="analyze_package")` identifies definitions.
3. `ast_inspect(path=..., symbol="analyze_package", source=True)` reads the body.
4. `ast_impact(path=..., symbols=["analyze_package"])` identifies potential dependents.
5. `ast_doc_impact(path=..., symbols=["analyze_package"])` locates prose to review.

These are tool-call expressions, not Python imports. Off the direct MCP surface,
wrap each name and argument mapping in `axm_call`. For source headers use
`ast_file_header(files=["src/axm_ast/__init__.py"], path=..., max_lines=80)`:
it returns leading lines, not a semantic import/export inventory.

## Workspace scope

Only `ast_context`, `ast_callers`, `ast_callees`, `ast_impact` and
`ast_graph` implement workspace aggregation. The dedicated CLI `callees`
stays single-package even though `ast_callees` is workspace-aware.
Use a member package for search, inspect, describe, flows and dead-code analysis.
See [scope and languages](scope-and-languages.md) for graph scopes and parser limits.

## Results and errors

AXM tools return `ToolResult` with `success`, `data`, optional `text` and
`error`. Check `success` before accessing `data`; batch results also require
checking their individual entries. The `axm_call` façade returns the rendered
text, not the complete structured payload. Direct MCP transport may wrap the
result again.

For example, `ast_inspect` puts one symbol under `data["symbol"]`; the
dedicated `axm-ast inspect --json` prints that inner symbol directly.
`ast_impact(detail="compact")` deliberately returns an empty `data` mapping
and a Markdown table in `text`. Do not parse compact prose as a stable JSON API.

## CLI and DAG access

The generic SDK CLI exposes registered tools as `axm <tool>`, for example
`axm ast_search --path . --name analyze_package`; inspect its own `--help`
before translating a dedicated CLI command. `tool_node` in `axm` adapts an
AXMTool into a DAG node. Neither route uses `axm.commands` or `axm.hooks`;
those discovery surfaces were removed.

The [tool reference](../reference/tools.md) lists every registered AST tool.
The [dedicated CLI reference](../reference/cli.md) documents `axm-ast`.
