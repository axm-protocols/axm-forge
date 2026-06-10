# Analyze Token Waste

Use `check` to analyze a payload and see how much each strategy would save — without modifying the input.

## CLI

```bash
# From stdin
echo '{"name": "Alice", "age": 30, "notes": null}' | axm-smelt check

# From a file
axm-smelt check --file data.json
```

Output:

```
Format: json
Tokens: 18
Strategies applied: none
Strategy estimates:
  minify: 22.2%
  drop_nulls: 16.7%
  strip_quotes: 5.6%
```

Only strategies with positive savings are shown — strategies that would produce no savings or increase tokens are automatically filtered out.

## Isolated estimates vs. real cumulative gain

The per-strategy `strategy_estimates` are measured **in isolation**, each against
the unmodified input. They are **independent and non-additive**: summing them
overstates the achievable reduction, because strategies overlap (for example
`minify` already removes whitespace that `collapse_whitespace` would also target).

For the figure you can actually expect, read `report.savings_pct`. It is the
**real cumulative gain** obtained by chaining the default strategy set (the
`safe` preset — exactly what `smelt(text)` applies with no explicit strategies),
so `check(text).savings_pct == smelt(text).savings_pct`. Already-minified input
yields `savings_pct == 0`.

## Python API

```python
from axm_smelt import check

report = check(data)

print(f"Format: {report.format.value}")
print(f"Tokens: {report.original_tokens}")

for strat, pct in report.strategy_estimates.items():
    if pct > 0:
        print(f"  {strat}: {pct:.1f}%")
```

## Difference from `smelt`

| | `check` | `smelt` |
|---|---|---|
| Modifies input | No | Yes |
| Returns `compacted` | Input unchanged | Compacted text |
| `strategy_estimates` | Populated (isolated, non-additive) | Empty |
| `savings_pct` | Real cumulative gain (default strategy set) | Real cumulative gain |
| `strategies_applied` | Always `[]` | Strategies that changed the output |

Use `check` to decide which preset or strategies to use, then call `smelt` to apply them.
