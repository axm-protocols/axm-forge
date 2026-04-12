# Describe Text Renderers

Text renderers that produce compact output for `ast_describe` results. Lives in `tools/describe_text.py`, following the same pattern as `tools/inspect_text.py`.

---

## `render_describe_text`

```python
from axm_ast.tools.describe_text import render_describe_text

render_describe_text(data: dict[str, Any], detail: str) -> str
```

Dispatcher — selects the correct renderer based on the `detail` parameter.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `data` | `dict[str, Any]` | *required* | Result data dict from `DescribeTool` (must contain `modules` key) |
| `detail` | `str` | *required* | Detail level: `"toc"`, `"summary"`, or `"detailed"` |

### Detail levels

| Detail | Output |
|---|---|
| `toc` | Module count header + one line per module: `name  Nf Nc  docstring` |
| `summary` | Module names with indented function signatures (annotations stripped) and class names |
| `detailed` | Module headers with docstring first lines, full function signatures with summary lines, classes with bases and methods |

### Return value

A compact multi-line string suitable for `ToolResult.text`. For `summary` mode, output is ≤50% of the equivalent JSON token count on representative packages.
