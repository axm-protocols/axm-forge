# Compact Data

Reduce token count from CLI or Python API.

## CLI

### From stdin

```bash
echo '{"name": "Alice", "age": 30}' | axm-smelt compact
```

The compacted text goes to stdout. Savings are reported to stderr:

```
{"name":"Alice","age":30}
Tokens: 14 -> 9 (35.7% saved)
```

### From a file

```bash
axm-smelt compact --file data.json
```

### Write output to a file

```bash
axm-smelt compact --file data.json --output compacted.json
```

The savings line is still printed to stderr; stdout is not used when `--output` is set.

### Choose a preset

```bash
# Lossless only
axm-smelt compact --file data.json --preset safe

# Structural transforms
axm-smelt compact --file data.json --preset moderate

# Maximum savings
axm-smelt compact --file data.json --preset aggressive
```

### Choose specific strategies

```bash
# Comma-separated strategy names
axm-smelt compact --file data.json --strategies minify,drop_nulls
```

## Python API

### Default preset (safe)

```python
from axm_smelt import smelt

report = smelt('{\n  "name": "Alice",\n  "age": 30\n}')
print(report.compacted)        # {"name":"Alice","age":30}
print(report.savings_pct)      # 35.71...
print(report.original_tokens)  # 14
print(report.compacted_tokens) # 9
```

### With a preset

```python
report = smelt(data, preset="moderate")
print(report.strategies_applied)  # ['minify', 'drop_nulls', ...]
```

### With explicit strategies

```python
report = smelt(data, strategies=["minify", "drop_nulls"])
```

## SmeltReport fields

| Field | Type | Description |
|---|---|---|
| `original` | `str` | Input text |
| `compacted` | `str` | Compacted text |
| `original_tokens` | `int` | Token count before |
| `compacted_tokens` | `int` | Token count after |
| `savings_pct` | `float` | Percentage saved |
| `format` | `Format` | Detected input format |
| `strategies_applied` | `list[str]` | Strategies that changed the output |
| `strategy_estimates` | `dict[str, float]` | Per-strategy savings estimates (from `check` only) |
