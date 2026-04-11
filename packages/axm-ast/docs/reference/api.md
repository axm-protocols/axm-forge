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
