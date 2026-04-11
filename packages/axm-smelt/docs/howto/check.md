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
| `strategy_estimates` | Populated | Empty |
| `strategies_applied` | Always `[]` | Strategies that changed the output |

Use `check` to decide which preset or strategies to use, then call `smelt` to apply them.
