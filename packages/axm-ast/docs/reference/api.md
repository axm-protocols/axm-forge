# API Reference

Public helpers exposed by `axm_ast.core.context`.

---

## `format_context_json`

```python
from axm_ast.core.context import format_context_json

format_context_json(ctx: dict[str, Any], *, depth: int | None = None) -> dict[str, Any]
```

Format a context dict (from `build_context`) into a JSON-serializable dict.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `ctx` | `dict[str, Any]` | *required* | Context dict produced by `build_context` |
| `depth` | `int \| None` | `None` | Detail level (see below) |

### Depth levels

| Depth | Detail |
|---|---|
| `None` | Full context with all modules and dependency graph |
| `0` | Top-5 modules by PageRank (~100 tokens) |
| `1` | Sub-packages with aggregate counts (~500 tokens) |
| `2` | Modules within sub-packages (~2 000 tokens) |
| `3+` | All modules with symbol names listed |

### Return value

A JSON-serializable dict with the following top-level keys:

| Key | Type | Description |
|---|---|---|
| `name` | `str` | Package name |
| `python` | `str \| None` | `requires-python` value, or `None` if not declared |
| `stack` | `dict` | Detected technology stack |
| `patterns` | `dict` | Module/function/class counts and layout |
| `top_modules` | `list[dict]` | Modules included at the requested depth |
| `graph` | `dict` | Dependency graph (depth `None` only) |

---

## `format_context_text`

```python
from axm_ast.core.context import format_context_text

format_context_text(data: dict[str, Any], *, depth: int = 0) -> str
```

Format a context dict (output of `format_context_json`) as compact plain text suitable for `ToolResult.text`.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `data` | `dict[str, Any]` | *required* | Formatted context dict from `format_context_json` |
| `depth` | `int` | `0` | Detail level matching the depth used for `format_context_json` |

### Output by depth

| Depth | Content |
|---|---|
| `0` | Header + top modules with star ratings |
| `1` | Header + sub-packages with module/symbol counts |
| `2+` | Header + sub-packages with inline symbol names `[sym1, sym2, … (+N)]` |

Header format: `{name} | {layout} | {N} mod · {N} fn · {N} cls`, followed by optional `python:` and `Stack:` lines when present.

---

## `build_workspace_context`

```python
from axm_ast.core.workspace import build_workspace_context

build_workspace_context(path: Path) -> dict[str, Any]
```

Build complete workspace context in one call. Lists all packages, their mutual dependencies, per-package stats, and the workspace-level dependency graph.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `path` | `Path` | *required* | Path to workspace root |

### Return value

| Key | Type | Description |
|---|---|---|
| `workspace` | `str` | Workspace name |
| `root` | `str` | Absolute path to workspace root |
| `package_count` | `int` | Number of member packages |
| `packages` | `list[dict]` | Per-package summary (name, root, module/function/class counts) |
| `package_graph` | `dict[str, list[str]]` | Inter-package dependency edges |

---

## `format_workspace_context`

```python
from axm_ast.core.workspace import format_workspace_context

format_workspace_context(ctx: dict[str, Any], *, depth: int = 1) -> dict[str, Any]
```

Apply depth-based filtering to a workspace context dict.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `ctx` | `dict[str, Any]` | *required* | Full workspace context from `build_workspace_context` |
| `depth` | `int` | `1` | Detail level (see below) |

### Depth levels

| Depth | Detail |
|---|---|
| `0` | Compact — package names only, no graph or stats |
| `>= 1` | Full output with all per-package stats and dependency graph |

---

## `search_symbols`

```python
from axm_ast.core.analyzer import search_symbols

search_symbols(
    pkg: PackageInfo,
    *,
    name: str | None = None,
    returns: str | None = None,
    kind: SymbolKind | None = None,
    inherits: str | None = None,
) -> list[tuple[str, FunctionInfo | ClassInfo | VariableInfo]]
```

Search for symbols across a package with filters. All filters are AND-combined.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `pkg` | `PackageInfo` | *required* | Analyzed package info |
| `name` | `str \| None` | `None` | Filter by symbol name (substring match) |
| `returns` | `str \| None` | `None` | Filter functions by return type (substring match) |
| `kind` | `SymbolKind \| None` | `None` | Filter by symbol kind (function, class, variable, etc.) |
| `inherits` | `str \| None` | `None` | Filter classes by base class name |

### Return value

A list of `(module_name, symbol)` tuples where `module_name` is the dotted module path (e.g. `pkg.sub.mod`) and `symbol` is a `FunctionInfo`, `ClassInfo`, or `VariableInfo`.

When serialized by the `ast_search` MCP tool, each symbol becomes a dict with:

| Key | Present when | Value |
|---|---|---|
| `name` | always | Symbol name |
| `module` | always | Dotted module path |
| `signature` | functions | Parameter signature |
| `return_type` | functions | Return annotation |
| `kind` | always | `FunctionKind` value (`function`, `method`, `property`, `classmethod`, `staticmethod`, `abstract`), `"class"`, or `"variable"` |
| `annotation` | variables with type | Type annotation |
| `value_repr` | variables with value | Short repr of assigned value |

### Fuzzy suggestions

When the `ast_search` MCP tool returns **0 results** and a `name` filter was provided, it automatically runs fuzzy matching against all symbols in the package using `difflib.get_close_matches` (cutoff 0.6). Suggestions are returned in `data["suggestions"]` alongside the empty `data["results"]`.

Internally, `_collect_module_candidates` builds the candidate map from each module's symbols. When a module's `name` attribute is `None` (common with tree-sitter parsed modules), it falls back to `module_dotted_name(mod.path, pkg.root)` to produce a proper dotted name (e.g. `axm_ast.core.analyzer`).

Each suggestion dict contains:

| Key | Type | Description |
|---|---|---|
| `name` | `str` | Original-cased symbol name |
| `score` | `float` | Similarity score (0–1) |
| `kind` | `str` | Symbol kind (`function`, `method`, `class`, `variable`, etc.) |
| `module` | `str` | Dotted module path where the symbol lives |

When `kind` is also specified, suggestions are filtered to that kind only. Duplicate symbol names across modules are deduplicated, keeping the entry with the highest score.

The `text` output for the 0-hit+suggestions case uses `?`-prefixed lines:

```
ast_search | name~"get_sesion" | 0 hits · 2 suggestions
? get_session            .92  func   core.analyzer
? get_sessions           .85  func   core.analyzer
```

---

## `format_workspace_text`

```python
from axm_ast.core.workspace import format_workspace_text

format_workspace_text(ctx: dict[str, Any]) -> str
```

Format a workspace context dict as compact plain text suitable for `ToolResult.text`.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `ctx` | `dict[str, Any]` | *required* | Workspace context from `build_workspace_context` or `format_workspace_context` |

### Output

Header line: `{workspace} | workspace | {N} packages`, followed by a `Packages:` listing with per-package stats and an optional `Dependencies:` section showing inter-package edges.

---

## `format_impact_compact`

```python
from axm_ast.tools.impact import format_impact_compact

format_impact_compact(
    impact: dict[str, Any] | list[dict[str, Any]],
) -> str
```

Format impact analysis as a compact markdown table.

Accepts either a single impact dict or a list of per-symbol reports.
When given a list, each symbol gets its own row with per-symbol callers.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `impact` | `dict[str, Any] \| list[dict[str, Any]]` | *required* | Single impact dict or list of per-symbol impact dicts |

### Return value

Markdown string with symbol table, caller details, and test footer. The `score` field (`LOW`, `MEDIUM`, `HIGH`) determines the displayed severity. When given a list, the maximum score across all reports is used as the headline score.

---

## `render_impact_text`

```python
from axm_ast.tools.impact import render_impact_text

render_impact_text(report: dict[str, Any]) -> str
```

Render a single impact report as human-readable text. Produces a compact key-value format with header, definition location, callers, affected modules, test files, git-coupled files, and cross-package impact.

Falls back to a minimal error line on malformed input.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `report` | `dict[str, Any]` | *required* | Single impact dict as returned by `_analyze_single` |

### Return value

Multi-line string starting with `ast_impact | {symbol} | {score}`, followed by definition, callers, and test information.

---

## `FlowsTool.execute`

```python
from axm_ast.tools.flows import FlowsTool

tool = FlowsTool()
result = tool.execute(
    path=".",
    entry=None,
    max_depth=5,
    cross_module=False,
    detail="trace",
    exclude_stdlib=True,
)
```

Detect entry points or trace execution flows from a symbol. Without `entry`, returns detected entry points. With `entry`, traces BFS flow from that symbol.

Registered as `ast_flows` via `axm.tools` entry point.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `path` | `str` | `"."` | Path to package directory |
| `entry` | `str \| None` | `None` | Entry point name to trace from; when `None`, detects entry points |
| `max_depth` | `int` | `5` | Maximum BFS depth for flow tracing |
| `cross_module` | `bool` | `False` | Resolve imports and trace into external modules |
| `detail` | `str` | `"trace"` | Detail level — `"trace"`, `"source"`, or `"compact"` |
| `exclude_stdlib` | `bool` | `True` | Exclude stdlib/builtin callees from BFS trace |

### Return value

`ToolResult` with:

| Key | Present when | Description |
|---|---|---|
| `entry_points` | no `entry` | List of detected entry point dicts |
| `entry` | with `entry` | Entry symbol name |
| `steps` / `compact` | with `entry` | Flow steps (trace/source) or compact tree string |
| `depth` | with `entry` | Actual max depth reached |
| `count` | always | Number of items returned |
| `truncated` | with `entry` | `True` when frontier nodes at `max_depth` had unexpanded children |

Returns `success=False` when the entry symbol is not found or `detail` is invalid.

Internally delegates to `_trace_entry` (single-entry BFS tracing with result formatting) and `_detect_entries` (entry point detection).

---

## `render_impact_batch_text`

```python
from axm_ast.tools.impact import render_impact_batch_text

render_impact_batch_text(reports: list[dict[str, Any]]) -> str
```

Render multiple impact reports as human-readable text. Produces a header with symbol count and maximum score, followed by per-symbol sections.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `reports` | `list[dict[str, Any]]` | *required* | List of per-symbol impact dicts |

### Return value

Multi-line string starting with `ast_impact | {n} symbols | max={score}`, followed by `## {symbol} | {score}` sections. Returns empty string for an empty list.

---

## `ImpactHook.execute`

```python
from axm_ast.hooks.impact import ImpactHook

hook = ImpactHook()
result = hook.execute(context, symbol="MyClass.method")
```

Run impact analysis on one or more symbols. When `symbol` contains newline characters, each line is analyzed separately and results are merged.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `context` | `dict[str, Any]` | *required* | Session context dictionary (must include `working_dir`) |
| `symbol` | `str` | *required* | Symbol name to analyze; newline-separated for batch |
| `path` | `str \| None` | `None` | Package path override (defaults to `working_dir` from context) |
| `detail` | `str` | `"full"` | `"compact"` for short format, otherwise full render |

### Return value

`HookResult` with:

| Field | Detail=full | Detail=compact |
|---|---|---|
| `metadata["impact"]` | Enriched report dict with `test_paths`, `packages` | Pre-formatted compact string |
| `metadata["packages"]` | Space-separated cross-package paths | *absent* |
| `text` | Human-readable render via `render_impact_text` (single) or `render_impact_batch_text` (multi) | `None` |

Returns `HookResult.fail(...)` when analysis raises an exception.
