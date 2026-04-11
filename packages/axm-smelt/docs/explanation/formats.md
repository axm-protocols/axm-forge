# Format Detection

`axm-smelt` auto-detects the input format before applying strategies.

## Supported Formats

| Format | `Format` enum value | Detection |
|---|---|---|
| JSON | `Format.JSON` | Starts with `{` or `[` after stripping whitespace |
| YAML | `Format.YAML` | Contains `---` separator or YAML-like `key: value` patterns |
| XML | `Format.XML` | Starts with `<` (excludes known HTML root tags) |
| TOML | `Format.TOML` | Contains `[section]` headers or `key = value` lines |
| CSV | `Format.CSV` | Multiple lines with consistent comma-separated columns |
| Markdown | `Format.MARKDOWN` | ≥2 distinct indicators: multi-level headings, pipe tables, fenced code blocks, inline links |
| Plain text | `Format.TEXT` | Fallback |

## Detection heuristics

Detection is heuristic and fast — no full parsing is required. The detector inspects:

1. The first non-whitespace character (for JSON, XML)
2. Line patterns (for YAML, TOML, CSV, Markdown)
3. Falls back to `TEXT` when no pattern matches

For JSON, the detector only checks the first character (`{` or `[`). If `json.loads()` subsequently fails inside a strategy, the strategy returns the input unchanged.

## Strategy behavior by format

Strategies that are format-specific gracefully skip non-matching inputs:

| Strategy | Works on | Behavior on other formats |
|---|---|---|
| `minify` | JSON | Returns input unchanged |
| `drop_nulls` | JSON | Returns input unchanged |
| `flatten` | JSON | Returns input unchanged |
| `tabular` | JSON | Returns input unchanged |
| `dedup_values` | JSON | Returns input unchanged |
| `strip_quotes` | JSON | Returns input unchanged |
| `round_numbers` | JSON | Returns input unchanged |

All current strategies target JSON. Running them on YAML, XML, or plain text is safe — the input is returned unmodified.

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
