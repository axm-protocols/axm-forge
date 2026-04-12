# Inspect Resolve Helpers

Internal helpers that resolve symbol names to inspect results. Used by `ast_inspect` when the input is a module name, dotted path, or class method reference.

---

## `inspect_module`

```python
from axm_ast.tools.inspect_resolve import inspect_module

inspect_module(
    pkg: PackageInfo, name: str, *, source: bool = False
) -> ToolResult | None
```

Try to resolve *name* as a module name and return module metadata. Returns `None` if no module matches, or a `ToolResult(success=False)` if multiple modules match ambiguously.

When `source=True`, the returned detail dict includes a `source` key with the module file content (truncated to 200 lines for large modules).

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `pkg` | `PackageInfo` | *required* | Analyzed package info |
| `name` | `str` | *required* | Module name to resolve (short or dotted) |
| `source` | `bool` | `False` | Attach module source code to the detail dict |

---

## `resolve_module_symbol`

```python
from axm_ast.tools.inspect_resolve import resolve_module_symbol

resolve_module_symbol(
    pkg: PackageInfo, dotted: str, *, source: bool = False
) -> ToolResult | None
```

Try to resolve `dotted` as `module_name.symbol_name`. Tries the longest module prefix first (e.g. `core.checker` before `core`). Returns `None` if no module prefix matches.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `pkg` | `PackageInfo` | *required* | Analyzed package info |
| `dotted` | `str` | *required* | Dotted path (e.g. `"tools.inspect_resolve.inspect_module"`) |
| `source` | `bool` | `False` | Attach source code to the resolved symbol |

---

## `_inspect_symbol`

```python
InspectTool._inspect_symbol(
    self, project_path: Path, symbol: str, *, source: bool = False
) -> ToolResult
```

Core symbol inspection logic within `InspectTool`. Loads the package, then dispatches to `inspect_dotted` (for dotted names) or `search_symbols` + module fallback (for simple names).

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `project_path` | `Path` | *required* | Root of the analyzed package |
| `symbol` | `str` | *required* | Symbol name to inspect |
| `source` | `bool` | `False` | Attach source code to the result |
