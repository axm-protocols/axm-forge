# Use Presets

Choose a preset by what the consumer can tolerate, then inspect the output.
A preset is an ordered list, not a guarantee of losslessness or maximum savings.

## Available presets

| Preset | Ordered strategies |
|---|---|
| `safe` | `minify`, `collapse_whitespace` |
| `moderate` | `minify`, `drop_nulls`, `flatten`, `dedup_values_with_refs`, `tabular`, `strip_quotes`, `collapse_whitespace`, `compact_tables`, `strip_html_comments` |
| `aggressive` | `minify`, `drop_nulls`, `flatten`, `tabular`, `round_numbers`, `dedup_values_with_refs`, `strip_quotes`, `collapse_whitespace`, `compact_tables`, `strip_html_comments` |

The order differs between moderate and aggressive. Earlier accepted strategies
can change what later ones can process. More strategies need not save more tokens.

## Choose and inspect

```python
from axm_smelt import smelt

data = '{"name": "Alice", "notes": null, "score": 3.14159265}'
for preset in ("safe", "moderate", "aggressive"):
    report = smelt(data, preset=preset)
    print(preset, report.compacted, report.savings_pct, report.strategies_applied)
```

- `safe` is the default starting point for whitespace compaction. Ordinary JSON
  values are retained after parsing, but representation, key order and duplicate
  object keys are not preserved. It is **not generally lossless**: XML whitespace,
  YAML inline comments and Markdown rendering can change.
- `moderate` additionally drops empty values, changes nesting, introduces
  aliases/tables, removes quotes and comments. Use only when those losses and
  representations are acceptable to the reader.
- `aggressive` also rounds floats to two decimal places when that candidate is
  accepted. Do not use for exact numeric computations.

For Markdown where hard line breaks or fence boundaries matter, retain the
original or choose and review narrower transformations. Details and known
limitations are in the [strategy catalog](../explanation/strategies.md).

## From the CLI

```bash
axm smelt --input-path ./payload.json --preset moderate --json-output
```

A nonempty explicit `--strategies` list overrides `--preset`. Python's
`strategies=[]` falls back to the preset/default rather than selecting none.

## Measure the selected pipeline

`check` reports positive **isolated** strategy estimates and Python's projected
**safe** gain. To compare presets, use the loop above; `check` does not simulate
each preset. Compaction returns new text and does not overwrite your input.
