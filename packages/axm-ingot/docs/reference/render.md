# `axm_ingot.render` — compact `ToolResult` text primitives

`axm_ingot.render` is a **stdlib-strict** toolbox for building the compact
`text` face of an AXM `ToolResult`. Callers supply Python values and choose how to attach the returned string
to their result. The module has no dependency on AXM or Pydantic. The six
root-exported primitives below compose a domain-specific renderer; the generic
walker and record table are additional submodule exports.

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

These primitives do not perform I/O for ordinary values. `compact_table` and
`labeled_block` render `None` cells as blank; the generic walker instead uses
an em dash. Inputs must follow the documented types. Conversion via `str()`
can raise or invoke user-defined behavior, and primitives do not catch it.
There is no common rule that every empty input produces an empty string.

---

## `header`

```text
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

```text
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

```text
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

```text
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

```text
format_count(n: int) -> str
```

Render an item count, abbreviating thousands with `K`/`M`/`B` suffixes. Values
with absolute value under 1000 are rendered verbatim. Negative values scale
identically (`-1500` → `-1.5K`); the largest suffix is `B`.

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

```text
format_size(num_bytes: int) -> str
```

Render a byte count in human units (base-1024), from `B` up to `PB`. Whole bytes
have no decimal; larger units carry one decimal place. Magnitude selects the
band for negative values as well (`-2048` → `-2.0 KB`). The labels are `KB` etc.
but the divisor is 1024. Values above the PB band remain expressed in PB.

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

## `render_result`

Import from `axm_ingot.render`; it is not re-exported at the root.

```python
from axm_ingot.render import render_result

assert render_result("check", True) == "check → yes"
assert render_result("check", {"ok": True}, label="result") == (
    "check | result\nok=yes"
)
```

Signature: `render_result(tool: str, data: object, *, label: str = "") -> str`.

The first line is the tool name, with ` | label` when supplied. A scalar uses
the arrow form above. Dictionaries retain insertion order; flat dictionaries
use `key=value · key=value` on one line. Nested containers use indentation. Short scalar lists (up to eight values) render inline;
homogeneous lists of at least two dictionaries with identical keys and scalar
values use a record table. Other lists use bullet items. Empty lists/tuples render `(none)`; an empty dictionary renders `(empty)`. No terminal newline is added.

Values use `str()`, except `None` → `—` and booleans → `yes`/`no`.
Separators and embedded newlines are not escaped. Text does not preserve types
or allow lossless round trips: for example `True` and `"yes"` look alike.

Ordinary exceptions while rendering the body (including recursive payloads)
are caught and return **the header only**, without an error indicator. This
does not cover header construction with invalid tool/label objects, nor
`BaseException` subclasses. Keep structured data for exact values and avoid
using text alone to decide whether rendering succeeded.

## `record_table`

Signature: `record_table(rows: Sequence[object], keys: Sequence[str], *,
indent: int = 0) -> list[str]`.

```python
from axm_ingot.render import record_table

assert record_table([{"name": "demo", "ok": True}], ["name", "ok"]) == [
    "name | ok", "demo | yes"
]
```

Returns lines, not one string: join them with `"\n".join(...)`. The first
line lists the selected keys with ` | `; each subsequent line projects one
record onto those keys. Extra fields are omitted. Missing keys, `None`
values and non-dictionary rows yield em-dash cells. Empty rows still produce
the header. Each indent level adds two spaces.

Direct calls do not verify homogeneity, scalar cells or escaping. Arbitrary
object conversion can raise. Use `compact_table` for padded alignment and
`record_table` for delimiter-separated records; neither is CSV or a safe
machine-readable interchange format.
