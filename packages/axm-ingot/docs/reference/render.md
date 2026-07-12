# `axm_ingot.render` — compact `ToolResult` text primitives

`axm_ingot.render` is a **stdlib-strict** toolbox for building the compact
`text` face of an AXM `ToolResult`. Each AXM tool fills `data` (a Pydantic
`model_dump`) but often leaves `text=None`, so the MCP server falls back to a
verbose JSON dump. These six primitives compose into a few-line métier renderer
that emits a token-cheap `text` instead.

Import them directly from the module:

```python
from axm_ingot.render import (
    compact_table,
    format_count,
    format_size,
    header,
    labeled_block,
    truncate,
)
```

All primitives are **pure and defensive**: `None` cells render as blank (never
the literal `"None"`), empty inputs degrade to `""`, and nothing raises on
hostile input.

---

## `header`

```python
header(tool: str, summary: str) -> str
```

Render the compact header line `{tool} | {summary}` — the first line of every
métier renderer.

| Parameter | Type | Description |
|---|---|---|
| `tool` | `str` | The tool name shown before the separator. |
| `summary` | `str` | A one-line summary shown after ` | `. |

**Returns** — `str`, the single `"{tool} | {summary}"` line.

```python
>>> header("audit", "3 findings")
'audit | 3 findings'
```

---

## `labeled_block`

```python
labeled_block(label: str, lines: Sequence[str | None]) -> str
```

Render *label* followed by *lines*, each indented two spaces. An empty *lines*
yields `""` so no dangling label is emitted; `None` entries render as blank
lines rather than the literal `"None"`.

| Parameter | Type | Description |
|---|---|---|
| `label` | `str` | The un-indented heading line. |
| `lines` | `Sequence[str | None]` | Body lines, each indented two spaces. |

**Returns** — `str`, the label joined with the indented body by newlines, or
`""` when *lines* is empty.

```python
>>> labeled_block("findings:", ["S101 at foo.py", "B008 at bar.py"])
'findings:\n  S101 at foo.py\n  B008 at bar.py'
>>> labeled_block("findings:", [])
''
```

---

## `compact_table`

```python
compact_table(
    rows: Sequence[Sequence[object]],
    headers: Sequence[object] | None = None,
) -> str
```

Render *rows* as a column-aligned table, optionally with a *headers* row.
Tolerates ragged rows (short rows are padded) and arbitrarily wide cells;
trailing whitespace is stripped per line.

| Parameter | Type | Description |
|---|---|---|
| `rows` | `Sequence[Sequence[object]]` | The data rows; cells are stringified. |
| `headers` | `Sequence[object] | None` | Optional header row rendered first. |

**Returns** — `str`, the aligned table (newline-joined), or `""` when there is
nothing to render.

```python
>>> print(compact_table(
...     [["foo.py", 3], ["bar.py", 12]],
...     headers=["file", "n"],
... ))
file    n
foo.py  3
bar.py  12
```

---

## `truncate`

```python
truncate(text: str, limit: int) -> str
```

Bound *text* to *limit* characters, appending an ellipsis (`…`) when it
overflows. Text at or under *limit* is returned unchanged; the overflow result
has at most `limit + 1` characters and ends with the ellipsis marker. A negative
*limit* is clamped to `0`.

| Parameter | Type | Description |
|---|---|---|
| `text` | `str` | The text to bound. |
| `limit` | `int` | Maximum length before the ellipsis is appended. |

**Returns** — `str`, either *text* unchanged or `text[:limit] + "…"`.

```python
>>> truncate("hello world", 5)
'hello…'
>>> truncate("hi", 5)
'hi'
```

---

## `format_count`

```python
format_count(n: int) -> str
```

Render an item count, abbreviating thousands with `K`/`M`/`B` suffixes. Values
under 1000 are rendered verbatim.

| Parameter | Type | Description |
|---|---|---|
| `n` | `int` | The count to format. |

**Returns** — `str`, the verbatim number or a one-decimal abbreviation.

```python
>>> format_count(42)
'42'
>>> format_count(1500)
'1.5K'
```

---

## `format_size`

```python
format_size(num_bytes: int) -> str
```

Render a byte count in human units (base-1024), from `B` up to `PB`. Whole bytes
have no decimal; larger units carry one decimal place.

| Parameter | Type | Description |
|---|---|---|
| `num_bytes` | `int` | The byte count to format. |

**Returns** — `str`, the human-readable size (e.g. `"512 B"`, `"2.0 KB"`).

```python
>>> format_size(512)
'512 B'
>>> format_size(2048)
'2.0 KB'
```
