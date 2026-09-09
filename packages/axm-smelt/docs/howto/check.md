# Analyze Token Waste

Use `check` to measure a payload before choosing a transformation.

## Compare estimates with the default pipeline

```python
from axm_smelt import check, smelt

data = '{"name": "Alice", "notes": null}'
report = check(data)
for strategy, savings in report.strategy_estimates.items():
    print(f"{strategy}: {savings:.2f}% in isolation")
print(f"Safe pipeline: {report.savings_pct:.2f}%")
assert report.compacted == data
assert report.savings_pct == smelt(data).savings_pct
```

Each estimate applies one strategy to the original input. Positive reductions
alone are included and rounded to two decimals. They overlap, so **do not add
them**. A structural strategy can also save whitespace by serializing JSON.
An absent estimate can mean inapplicable, unchanged, equal-token, or larger output.

`report.savings_pct` measures the chained **safe** preset; it does not estimate
`moderate` or `aggressive`. To evaluate those, call `smelt(data, preset=...)`
and inspect the returned text. Neither function mutates your source object.

## From CLI or MCP

```bash
printf '{"name": "Alice", "notes": null}\n' | axm smelt_check --json-output
axm smelt_check --input-path ./payload.json
```

The tool returns `format`, `tokens`, and `strategy_estimates`.
**Cumulative savings is available in Python's report only.** To obtain actual
pipeline metrics through MCP/CLI, call `smelt` with the chosen preset.
The text “no waste detected” means no registered strategy produced a positive
isolated reduction; it does not mean the content is minimal or semantically safe.

## Difference from smelt

| Report behavior | `check` | `smelt` |
|---|---|---|
| `compacted` | Input unchanged | Accepted output text |
| `compacted_tokens` | Input count | Output count |
| `strategy_estimates` | Positive isolated estimates | Empty |
| `savings_pct` | Projected safe pipeline gain | Actual selected pipeline gain |
| `strategies_applied` | Empty | Accepted transforms |

Continue with [presets](presets.md) and [report contracts](../reference/contracts.md).
