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

The returned `ToolResult` includes a `text` field with a human-readable summary produced by `render_module_text(detail)`.

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

The returned `ToolResult` includes a `text` field with a human-readable summary produced by `render_symbol_text(detail)`.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `pkg` | `PackageInfo` | *required* | Analyzed package info |
| `dotted` | `str` | *required* | Dotted path (e.g. `"tools.inspect_resolve.inspect_module"`) |
| `source` | `bool` | `False` | Attach source code to the resolved symbol |

---

## `InspectTool.execute`

```python
InspectTool.execute(
    self,
    *,
    path: str = ".",
    symbol: str | None = None,
    symbols: list[str] | None = None,
    source: bool = False,
) -> ToolResult
```

Main entry point for `ast_inspect`. Dispatches to `_inspect_symbol` (single) or `_inspect_batch` (batch) depending on the arguments. When neither `symbol` nor `symbols` is provided, returns an error.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `path` | `str` | `"."` | Path to package directory |
| `symbol` | `str \| None` | `None` | Single symbol name to inspect (supports dotted paths) |
| `symbols` | `list[str] \| None` | `None` | List of symbol names for batch inspection |
| `source` | `bool` | `False` | Include source code in results |

---

## `_inspect_symbol`

```python
InspectTool._inspect_symbol(
    self, project_path: Path, symbol: str, *, source: bool = False
) -> ToolResult
```

Core symbol inspection logic within `InspectTool`. Loads the package, then dispatches to `inspect_dotted` (for dotted names) or `search_symbols` + module fallback (for simple names).

The returned `ToolResult` includes a `text` field with a human-readable summary produced by `render_symbol_text(detail)`.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `project_path` | `Path` | *required* | Root of the analyzed package |
| `symbol` | `str` | *required* | Symbol name to inspect |
| `source` | `bool` | `False` | Attach source code to the result |

---

## `resolve_class_method`

```python
from axm_ast.tools.inspect_resolve import resolve_class_method

resolve_class_method(
    pkg: PackageInfo, dotted: str, *, source: bool = False
) -> ToolResult | None
```

Try to resolve `dotted` as `ClassName.method_name`. Returns `None` if no class matches, or a `ToolResult(success=False)` if the class exists but the method is not found.

The returned `ToolResult` includes a `text` field with a human-readable summary produced by `render_symbol_text(detail)`.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `pkg` | `PackageInfo` | *required* | Analyzed package info |
| `dotted` | `str` | *required* | Dotted path (e.g. `"MyClass.my_method"`) |
| `source` | `bool` | `False` | Attach source code to the resolved method |

---

## `InspectTool._inspect_batch`

```python
InspectTool._inspect_batch(
    self, project_path: Path, symbols: list[str], *, source: bool
) -> ToolResult
```

Inspect multiple symbols in batch. Iterates over `symbols`, calling `_inspect_symbol` for each, and collects the results.

The returned `ToolResult` includes a `text` field with a human-readable summary produced by `render_batch_text(results)`, with each symbol separated by a blank line.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `project_path` | `Path` | *required* | Root of the analyzed package |
| `symbols` | `list[str]` | *required* | List of symbol names to inspect |
| `source` | `bool` | *required* | Attach source code to each result |
