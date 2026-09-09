# AXM tool reference

These names are registered under `axm.tools` in the package metadata.
Invoke off-surface tools with `axm_call(name=..., arguments={...})`.
All paths default to `"."`; use `axm_describe` for the installed invocation
contract. The signatures below describe named inputs, not executable Python.

| Tool | Inputs beyond `path` | Purpose |
|---|---|---|
| `ast_context` | `depth=1` (or null for full data) | Package/workspace overview |
| `ast_describe` | `detail="summary"`, `compress=False`, `modules=None` | Package descriptions |
| `ast_search` | `name=None`, `returns=None`, `kind=None`, `inherits=None` | AND-combined symbol filters |
| `ast_inspect` | `symbol=None`, `symbols=None`, `source=False` | Exact definition or module inspection |
| `ast_callers` | `symbol` required | Call sites across package/workspace |
| `ast_callees` | `symbol` required | Calls made by a symbol, package/workspace |
| `ast_graph` | `format="json"`, `scope=None` | Package/workspace graphs |
| `ast_impact` | `symbol=None`, `symbols=None`, `exclude_tests=False`, `detail=None`, `include_module_importers=False`, `precise_callers=False` | Change impact |
| `ast_dead_code` | `include_tests=False` | Unreferenced symbol candidates |
| `ast_flows` | `entry=None`, `max_depth=5`, `cross_module=False`, `detail="trace"`, `exclude_stdlib=True` | Entry detection or BFS tracing |
| `ast_diff` | `base` and `head` required (empty defaults rejected) | Compare committed git refs |
| `ast_docs` | `detail="full"`, `pages=None` | Markdown discovery and content |
| `ast_doc_impact` | `symbols=None` | Lexical documentation references |
| `ast_file_header` | `files` required, `max_lines=30` | Leading lines of relative file paths |
| `ast_coupling_gaps` | `symbol=None`, `symbols=None` | Lower-bound structural/contract coupling |

`modules`, `pages`, `symbols` and `files` are lists, not comma-separated
strings. `ast_impact` additionally consumes `test_filter` via keyword options:
`"none"`, `"all"`, or `"related"`. Unknown keyword options may be ignored.

## Description and inspection

`ast_describe` supports `toc`, `names`, `summary` and `detailed`;
`full` is rejected. `compress=True` requires `detail="summary"`
(the tool default). The dedicated CLI defaults to `detailed` and permits
compression with `summary` or `detailed`. Budget and rank are dedicated CLI
formatting options, not tool inputs.

`ast_inspect` requires a symbol or a nonempty symbol list; unlike the
dedicated CLI, omitting both is an error. Exact ambiguous bare names produce
an error with candidates; qualify by module. Prefer one selector at a time:
the tool chooses `symbols` when provided, while the CLI rejects both.
Module metadata contains names/counts; `source=True` attaches the first 200
module lines, with a truncation notice, in the structured symbol data. The
module text renderer omits that source, so the text-only façade does not expose
it; use selected function/class inspection for source through the façade.
Function/class source follows the
symbol's source range.

## Impact and coupling

A bare ambiguous impact target expands to per-definition reports. A single
full result is in `data`; a batch uses `data["symbols"]`. Compact impact has
only text and empty data. `precise_callers=True` excludes callers whose imports
prove a distinct homonym; unresolved imports remain included.
`include_module_importers=True` adds module-only dependents in single-package
mode; it is currently inert in workspace mode.

Coupling gaps adds `reference_coupled`, `protocol_coupled` and
`value_coupled` collections. Omitting its selectors scans the package's public
API. Its lower-bound report is not evidence of exhaustive coupling.

## Documentation tools

`ast_docs` has `toc`, `summary`, `full` modes and page-name substring
filters. It reads Markdown/configuration; generated MkDocs pages are build
artifacts and must be checked in the built site.

`ast_doc_impact` reports `doc_refs`, `undocumented` and
`stale_signatures`. These are lexical signals, not a verdict on prose truth.
See [the limits](../explanation/doc_impact_limits.md).

`ast_file_header` returns `headers` entries containing `file` and `header`;
missing or binary files are skipped. It is a bounded leading-line read, not
an AST export resolver.

## Output contracts

Tools return `ToolResult(success, data, text, error)`; the façade presents
text. Dedicated CLI JSON often unwraps the payload or uses a different shape.
Examples and transport details are in [MCP usage](../howto/mcp.md).
Generated implementation reference is available under **Python API** in the
navigation; the root [Python guide](api.md) distinguishes stable exports from
internal helpers.
