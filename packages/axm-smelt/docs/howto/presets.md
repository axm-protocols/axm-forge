# Use Presets

Presets are named collections of strategies ordered for best results.

## Available Presets

| Preset | Strategies | Use when |
|---|---|---|
| `safe` | `minify` | Output must be semantically identical |
| `moderate` | `minify`, `drop_nulls`, `flatten`, `dedup_values`, `tabular`, `strip_quotes` | Structural transforms are acceptable |
| `aggressive` | `minify`, `drop_nulls`, `flatten`, `tabular`, `round_numbers`, `dedup_values`, `strip_quotes` | Maximum savings, float precision may change |

## CLI

```bash
# Default (safe) — just minify
axm-smelt compact --file data.json

# Moderate
axm-smelt compact --file data.json --preset moderate

# Aggressive
axm-smelt compact --file data.json --preset aggressive
```

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
- The downstream consumer needs byte-identical semantics (e.g., signature verification)
- The data contains floats that must not be rounded
- You only want whitespace removed

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

```bash
axm-smelt check --file data.json
```

```python
from axm_smelt import check

report = check(data)
for strat, pct in report.strategy_estimates.items():
    print(f"  {strat}: {pct:.1f}%")
```
