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

Build detail dict from a `FunctionInfo`. Returns keys: `name`, `file`, `start_line`, `end_line`, `signature`, and optionally `docstring`, `return_type`, `parameters`.

---

## `class_detail`

```python
class_detail(sym: ClassInfo, *, file: str = "") -> dict[str, Any]
```

Build detail dict from a `ClassInfo`. Returns keys: `name`, `file`, `start_line`, `end_line`, and optionally `docstring`, `bases`, `methods`.
