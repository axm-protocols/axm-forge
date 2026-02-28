# Use via MCP

`axm-ast` exposes all CLI commands as MCP (Model Context Protocol) tools via `axm-mcp`. AI agents can call them directly without spawning subprocesses.

## Available Tools

| MCP Tool | Equivalent CLI | Purpose |
|---|---|---|
| `ast_context(path, slim?)` | `axm-ast context` | One-shot project dump (stack, layout, patterns, modules) |
| `ast_describe(path, detail?, compress?, modules?)` | `axm-ast describe` | Full API surface (signatures, docstrings, `__all__`) |
| `ast_search(path, name?, returns?, kind?, inherits?)` | `axm-ast search` | Semantic symbol lookup |
| `ast_callers(path, symbol)` | `axm-ast callers` | Find all call-sites of a symbol |
| `ast_impact(path, symbol)` | `axm-ast impact` | Change blast radius analysis |
| `ast_inspect(path, symbol)` | `axm-ast inspect` | Full detail on a single symbol |
| `ast_graph(path)` | `axm-ast graph` | Import dependency graph |
| `ast_docs(path)` | `axm-ast docs` | Documentation tree dump |
| `ast_dead_code(path)` | `axm-ast dead-code` | Detect unreferenced symbols |
| `ast_diff(path, base, head)` | `axm-ast diff` | Structural branch diff at symbol level |

!!! tip "ast_describe detail levels"
    `ast_describe` accepts `detail`: `"toc"` (module names + counts only), `"summary"` (signatures only),
    `"detailed"` (+ docstrings, params, return types — **default**), or `"full"` (+ line
    numbers, imports, variables). Use `modules=["core"]` to filter by module name substring.
    Use `compress=True` for an AI-optimized view with signatures and first docstring lines.


## Workspace Support

All tools with a `path` parameter **auto-detect `uv` workspaces**. When `path` points to a directory with a `pyproject.toml` containing `[tool.uv.workspace]`, the tools automatically switch to workspace mode:

- **`ast_context`** — returns a unified context with all member packages, their dependency graph, and aggregated statistics
- **`ast_callers`** — searches across all packages, prefixing modules with `pkg_name::` for disambiguation
- **`ast_impact`** — performs cross-package impact analysis, identifying callers, re-exports, and test files across the workspace
- **`ast_graph`** — generates an inter-package dependency graph (Mermaid or adjacency list)

No special arguments needed — just point `path` to the workspace root.

## When to Use What

| Task | Start with | Then use |
|---|---|---|
| **Onboarding** | `ast_context` | `ast_describe` |
| **Writing code** | `ast_describe` → `ast_search` | `ast_impact` before modifying |
| **Refactoring** | `ast_impact` → `ast_callers` | `ast_graph` for architecture |
| **Writing docs** | `ast_docs` → `ast_context` | `ast_describe` for API details |
| **Debugging** | `ast_search` → `ast_callers` | `ast_inspect` for detail |

## Why MCP over `grep_search`?

- `grep_search("X")` finds text in imports, comments, strings, docstrings, AND calls — noisy
- `ast_callers(symbol="X")` finds only **actual call-sites** with context (file, line, enclosing function)
- `ast_search(returns="X")` finds only **functions returning type X** — AST-precise

## Output Format

All tools return JSON. The structure matches the `--json` CLI output for the corresponding command.

```json
{
  "success": true,
  "modules": [
    {
      "name": "core.analyzer",
      "functions": [{"name": "analyze_package", "signature": "..."}],
      "classes": []
    }
  ]
}
```

!!! tip "Tool Discovery"
    Use `list_tools()` in the MCP server to see all available tools with descriptions.
