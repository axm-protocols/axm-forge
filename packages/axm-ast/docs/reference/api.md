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
