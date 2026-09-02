# Use Presets

Presets are named collections of strategies ordered for best results.

## Available Presets

| Preset | Strategies | Use when |
|---|---|---|
| `safe` | `minify`, `collapse_whitespace` | Keeps the parsed value identical (not byte/whitespace-lossless) |
| `moderate` | `minify`, `drop_nulls`, `flatten`, `dedup_values_with_refs`, `tabular`, `strip_quotes`, `collapse_whitespace`, `compact_tables`, `strip_html_comments` | Structural transforms are acceptable |
| `aggressive` | `minify`, `drop_nulls`, `flatten`, `tabular`, `round_numbers`, `dedup_values_with_refs`, `strip_quotes`, `collapse_whitespace`, `compact_tables`, `strip_html_comments` | Maximum savings, float precision may change |

## AXMTool

Pass the preset name to the registered `smelt` tool through MCP or a DAG node. The same entry point also provides generated AXM CLI help:

```bash
axm smelt --help
```

The removed standalone CLI and its `--file` option have no compatibility shim; callers read files before invoking the tool.

## Python API

```python
from axm_smelt import smelt

# Safe
report = smelt(data, preset="safe")

# Moderate
report = smelt(data, preset="moderate")

# Aggressive
report = smelt(data, preset="aggressive")
```

## Choosing a Preset

**Use `safe`** when:
- The downstream consumer needs the parsed value preserved (structure and
  scalars identical), while whitespace may change
- The data contains floats that must not be rounded
- You only want whitespace removed

> `safe` keeps the *parsed value* identical, not the bytes. For YAML it will
> not compact a document carrying `#` comments (comments are content a
> parse+dump would silently drop), so commented YAML is returned unchanged
> rather than stripped.

**Use `moderate`** when:
- Null/empty values are not meaningful and can be dropped
- Repeated nested structures can be flattened
- Repeated long strings benefit from aliasing
- You want significant savings without altering numeric precision

**Use `aggressive`** when:
- You want the maximum token reduction
- Float precision beyond 2 decimal places is not needed
- The data is large and savings matter more than exact fidelity

## Inspecting what a preset would do

Use `check` to see estimates for each strategy before committing:

Through the tool registry, call `smelt_check` with the payload as its `data` input. The generated CLI surface can be inspected with:

```bash
axm smelt_check --help
```

```python
from axm_smelt import check

report = check(data)
for strat, pct in report.strategy_estimates.items():
    print(f"  {strat}: {pct:.1f}%")
```
