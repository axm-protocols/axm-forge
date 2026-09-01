# Legacy Hooks

The deprecated `axm.hooks` adapters have been removed from `axm-ast`. The
analysis capabilities remain available as request/response AXM tools registered
through `axm.tools`; use those tools directly from MCP, the `axm` CLI, or a
DAG via `tool_node`.

| Removed hook entry point | Direct AXM tool |
|---|---|
| `ast:context` | `ast_context` |
| `ast:flows` | `ast_flows` |
| `ast:trace-source` | `ast_flows` with `detail="source"` |
| `ast:source-body` | `ast_inspect` with source output enabled |
| `ast:impact` | `ast_impact` |
| `ast:doc-impact` | `ast_doc_impact` |
| `ast:file-header` | `ast_file_header` |

The removed Python classes (`ContextHook`, `FlowsHook`, `TraceSourceHook`,
`SourceBodyHook`, `ImpactHook`, `DocImpactHook`, and `FileHeaderHook`)
are no longer importable. See the [API reference](api.md) for the retained tool
interfaces.
