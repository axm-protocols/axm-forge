# Format Detection

`axm-smelt` auto-detects the input format before applying strategies.

## Supported Formats

| Format | `Format` enum value | Detection |
|---|---|---|
| JSON | `Format.JSON` | Starts with `{` or `[` after stripping whitespace |
| YAML | `Format.YAML` | Contains `---` separator or YAML-like `key: value` patterns |
| XML | `Format.XML` | Starts with `<` (excludes known HTML root tags) |
| TOML | `Format.TOML` | Parses cleanly with `tomllib.loads` |
| CSV | `Format.CSV` | `csv.Sniffer` finds a delimiter and ≥2 rows share a consistent column count |
| Markdown | `Format.MARKDOWN` | ≥2 distinct indicators: multi-level headings, pipe tables, fenced code blocks, inline links |
| Plain text | `Format.TEXT` | Fallback |

## Detection heuristics

Detection is heuristic and fast — no full parsing is required. The detector inspects:

1. The first non-whitespace character (for JSON, XML)
2. Line patterns (for YAML, TOML, CSV, Markdown)
3. Falls back to `TEXT` when no pattern matches

For JSON, the detector only checks the first character (`{` or `[`). If `json.loads()` subsequently fails inside a strategy, the strategy returns the input unchanged.

## Strategy behavior by format

Each strategy targets specific formats and returns the input unchanged on any
other format (a no-op that the keep-if-reduced guard treats as skipped):

| Strategy | Category | Works on | Behavior on other formats |
|---|---|---|---|
| `minify` | whitespace | JSON, YAML, XML | Returns input unchanged |
| `drop_nulls` | structural | JSON | Returns input unchanged |
| `flatten` | structural | JSON | Returns input unchanged |
| `tabular` | structural | JSON | Returns input unchanged |
| `dedup_values_with_refs` | structural | JSON | Returns input unchanged |
| `round_numbers` | cosmetic | JSON | Returns input unchanged |
| `strip_quotes` | cosmetic | JSON | Returns input unchanged |
| `collapse_whitespace` | whitespace | prose / Markdown (skips structured formats) | Returns input unchanged |
| `compact_tables` | whitespace | Markdown | Returns input unchanged |
| `strip_html_comments` | cosmetic | prose / Markdown | Returns input unchanged |

`minify` handles YAML and XML in addition to JSON; the three prose strategies
(`collapse_whitespace`, `compact_tables`, `strip_html_comments`) target
Markdown / plain text. Running a JSON-only strategy on YAML, XML, or plain text
is safe — the input is returned unmodified.

`strip_quotes` is JSON-only by construction: its ``"word":`` pattern would also
match quoted words in prose, so it is guarded to `Format.JSON` and never mutates
non-JSON text.

## Accessing detected format

```python
from axm_smelt import smelt
from axm_smelt.core.models import Format

report = smelt(data)
print(report.format)          # Format.JSON
print(report.format.value)    # "json"

if report.format == Format.JSON:
    print("JSON detected")
```
