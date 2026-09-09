# Describe Text Renderers

Text renderers that produce compact output for `ast_describe` results. Lives in `tools/describe_text.py`, following the same pattern as `tools/inspect_text.py`.

---

## `render_describe_text`

```text
render_describe_text(data: dict[str, object], detail: str) -> str
```

Import this internal helper from `axm_ast.tools.describe_text`.

Dispatcher — selects the correct renderer based on the `detail` parameter.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `data` | `dict[str, Any]` | *required* | Result data dict from `DescribeTool` (must contain `modules` key) |
| `detail` | `str` | *required* | Detail level: `"toc"`, `"names"`, `"summary"`, or `"detailed"` |

### Detail levels

| Detail | Output |
|---|---|
| `toc` | Header + one line per module: `name  (Nfn Ncls)  docstring` — zero counts omitted, `—` for empty |
| `summary` | `## module` headers with indented signatures (`def ` stripped) and `class Name(bases)` — empty modules skipped |
| `detailed` | `## module — docstring` headers, signatures with `# summary` comments, class methods prefixed with `.` — modules with no symbols and no docstring skipped |

### Return value

A compact multi-line string suitable for `ToolResult.text`. Output size varies with symbols and metadata; no fixed compression ratio is guaranteed.
