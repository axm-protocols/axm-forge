# Strategy Catalog

Detailed reference for all 10 compaction strategies.

## Zero-reparse pipeline

Strategies that operate on parsed JSON data read `ctx.parsed` directly
and propagate their result as `parsed` on the returned context. This
means that when multiple JSON-aware strategies run in sequence (e.g.
`minify` → `drop_nulls` → `flatten`), the data is parsed from text
**exactly once** — subsequent strategies reuse the in-memory object.
Text-only strategies like `strip_quotes` trigger a single serialization
when they access `ctx.text`.

## minify

**Category:** whitespace
**Lossless:** yes

Removes unnecessary whitespace from JSON by parsing and re-serializing with compact separators (`(",", ":")`). Non-JSON inputs are returned unchanged.

**Example:**

```
Input:  {"name": "Alice", "age": 30}   (30 chars, 14 tokens)
Output: {"name":"Alice","age":30}       (22 chars, 9 tokens)
```

**When to use:** Always. Include `minify` first in any custom strategy list — it normalizes whitespace so other strategies work on compact JSON.

---

## drop_nulls

**Category:** structural
**Lossless:** yes (if nulls carry no meaning)

Recursively removes keys whose values are `None`, `""`, `[]`, or `{}` from dicts and lists. Operates on parsed JSON; non-JSON inputs are returned unchanged.

**Example:**

```json
Input:  {"name": "Alice", "notes": null, "tags": []}
Output: {"name": "Alice"}
```

**When to use:** API responses where absent and null are equivalent. Avoid when downstream code distinguishes `null` from a missing key.

---

## flatten

**Category:** structural
**Lossless:** yes (if key paths are reconstructable)

Collapses single-child wrapper dicts by joining keys with `.`.

**Example:**

```json
Input:  {"user": {"profile": {"name": "Alice"}}}
Output: {"user.profile.name": "Alice"}
```

Dicts with multiple keys are not flattened.

**When to use:** Deeply nested API responses with single-key wrappers. Avoid when the nested key structure is semantically meaningful to the consumer.

---

## tabular

**Category:** structural
**Lossless:** yes (headers are preserved)

Converts a homogeneous `list[dict]` to a compact pipe-separated table with a header row. Recurses into nested dicts.

**Example:**

```json
Input:  [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
Output: name|age\nAlice|30\nBob|25
```

Best savings on large arrays of uniform records (e.g., database query results, CSV-like data).

**When to use:** Large arrays of records with the same schema. Not useful for heterogeneous arrays or arrays of scalars.

---

## dedup_values

**Category:** structural
**Lossless:** yes (aliases are defined in `_refs`)

Replaces frequently repeated long string values (>=20 chars, >=2 occurrences) with short aliases (`$R0`, `$R1`, ...). Prepends a `_refs` dict mapping aliases back to original values.

**Example:**

```json
Input:  {"a": "a-very-long-repeated-value", "b": "a-very-long-repeated-value"}
Output: {"_refs": {"$R0": "a-very-long-repeated-value"}, "_data": {"a": "$R0", "b": "$R0"}}
```

Aliases are assigned by savings potential (length x occurrences) descending.

**When to use:** Payloads containing repeated long strings such as URLs, UUIDs, or descriptions. Savings increase with string length and repetition count.

---

## strip_quotes

**Category:** cosmetic
**Lossless:** yes for JSON parsers that accept unquoted keys (non-standard)

Removes quotes from JSON keys that consist only of alphanumeric characters and underscores.

**Example:**

```
Input:  {"name": "Alice"}
Output: {name: "Alice"}
```

!!! warning
    The output is not valid JSON. Use only when the consumer accepts relaxed JSON syntax (e.g., LLM-interpreted payloads, not API calls).

**When to use:** LLM context injection where exact JSON validity is not required.

---

## round_numbers

**Category:** cosmetic
**Lossless:** no (float precision is reduced)

Rounds all float values to N decimal places (default: 2). Integer values are not modified.

**Example:**

```json
Input:  {"x": 3.14159265, "y": 2.71828182}
Output: {"x": 3.14, "y": 2.72}
```

**When to use:** Scientific or financial data where high precision is not needed in context. Avoid when downstream code uses the values for computation.

---

## collapse_whitespace

**Category:** whitespace
**Lossless:** yes

Reduces consecutive blank lines (3+) to a single blank line and strips trailing whitespace from each line. Fenced code blocks are preserved unchanged. Skips structured formats (JSON, YAML, XML, TOML, CSV).

**Example:**

```
Input:  # Title\n\n\n\n\nParagraph one.\n\n\n\nParagraph two.
Output: # Title\n\nParagraph one.\n\nParagraph two.
```

**When to use:** Markdown and plain-text content with excessive vertical whitespace. Included in all presets (`safe`, `moderate`, `aggressive`).

---

## compact_tables

**Category:** whitespace
**Lossless:** yes

Strips padding whitespace from markdown table cells. Only applies to `MARKDOWN` format. Fenced code blocks are skipped.

**Example:**

```
Input:  |  Name   |  Age  |
Output: |Name|Age|
```

**When to use:** Markdown content with padded tables. Included in `moderate` and `aggressive` presets.

---

## strip_html_comments

**Category:** cosmetic
**Lossless:** no (comments are removed)

Removes HTML comments (`<!-- ... -->`) from markdown and plain-text content. Cleans up blank lines left by removal. Fenced code blocks are preserved.

**Example:**

```
Input:  <!-- TODO: review -->\nSome text.
Output: Some text.
```

**When to use:** Markdown with draft notes or internal comments that should not be included in LLM context. Included in `moderate` and `aggressive` presets.
