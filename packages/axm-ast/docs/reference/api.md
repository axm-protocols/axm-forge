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
