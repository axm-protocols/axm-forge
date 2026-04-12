# Inspect Detail Helpers

Internal helpers that build detail dicts for `ast_inspect` results.

---

## `build_detail`

```python
from axm_ast.tools.inspect_detail import build_detail

build_detail(
    sym: FunctionInfo | ClassInfo | VariableInfo,
    *,
    file: str = "",
    abs_path: str = "",
    source: bool = False,
) -> dict[str, Any]
```

Dispatch to the appropriate `*_detail` function based on symbol type. When `source=True` and `abs_path` is provided, attaches source code for functions, classes, and variables.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `sym` | `FunctionInfo \| ClassInfo \| VariableInfo` | *required* | Parsed symbol node |
| `file` | `str` | `""` | Relative file path |
| `abs_path` | `str` | `""` | Absolute file path (needed when `source=True`) |
| `source` | `bool` | `False` | Attach source code to the detail dict |

---

## `read_source`

```python
from axm_ast.tools.inspect_detail import read_source

read_source(abs_file_path: str, start: int, end: int) -> str
```

Read source lines from a file by absolute path. Returns the joined lines from `start` to `end` (1-based, inclusive). Returns an empty string on `OSError` or `IndexError`.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `abs_file_path` | `str` | *required* | Absolute path to the source file |
| `start` | `int` | *required* | First line number (1-based) |
| `end` | `int` | *required* | Last line number (1-based, inclusive) |

---

## `variable_detail`

```python
variable_detail(sym: VariableInfo, *, file: str = "") -> dict[str, Any]
```

Build detail dict from a `VariableInfo`. Returns keys: `name`, `file`, `kind`, `start_line`, `end_line`, and optionally `annotation` and `value_repr`.

---

## `function_detail`

```python
function_detail(sym: FunctionInfo, *, file: str = "") -> dict[str, Any]
```

Build detail dict from a `FunctionInfo`. Returns keys: `name`, `kind`, `file`, `start_line`, `end_line`, `signature`, and optionally `docstring`, `return_type`, `parameters`.

---

## `class_detail`

```python
class_detail(sym: ClassInfo, *, file: str = "") -> dict[str, Any]
```

Build detail dict from a `ClassInfo`. Returns keys: `name`, `kind`, `file`, `start_line`, `end_line`, and optionally `docstring`, `bases`, `methods`.

---

## `build_module_detail`

```python
from axm_ast.tools.inspect_detail import build_module_detail

build_module_detail(pkg: PackageInfo, mod: ModuleInfo, name: str) -> dict[str, Any]
```

Build detail dict for a module. Returns keys: `name`, `kind` (`"module"`), `file`, `start_line`, `end_line`, `docstring`, `functions`, `classes`, `variables`, `imports`.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `pkg` | `PackageInfo` | *required* | Analyzed package info |
| `mod` | `ModuleInfo` | *required* | Module node |
| `name` | `str` | *required* | Display name for the module |

---

## Text Renderers

Pure functions that convert detail dicts (as returned by the helpers above) into compact, human-readable text. Imported via `axm_ast.tools.inspect_detail`.

---

### `render_function_text`

```python
render_function_text(detail: dict[str, Any]) -> str
```

Render a function detail dict as compact text: header line, signature, truncated docstring, params, return type. Appends a fenced Python source block when `source` is present.

---

### `render_class_text`

```python
render_class_text(detail: dict[str, Any]) -> str
```

Render a class detail dict as compact text: header with bases, truncated docstring, methods list. Appends source block when present.

---

### `render_variable_text`

```python
render_variable_text(detail: dict[str, Any]) -> str
```

Render a variable detail dict: header with `variable` suffix, annotation, and/or value repr.

---

### `render_module_text`

```python
render_module_text(detail: dict[str, Any]) -> str
```

Render a module detail dict: header with symbol count, truncated docstring, function and class lists.

---

### `render_symbol_text`

```python
render_symbol_text(detail: dict[str, Any]) -> str
```

Dispatcher — selects the correct renderer based on the `kind` key in the detail dict (`function`, `method`, `class`, `variable`, `module`).

---

### `render_batch_text`

```python
render_batch_text(symbols: list[dict[str, Any]]) -> str
```

Join multiple symbol renders with blank-line separators. Error entries (dicts with an `error` key) are rendered as `{name}  ⚠ {error}`. Returns empty string for an empty list.
