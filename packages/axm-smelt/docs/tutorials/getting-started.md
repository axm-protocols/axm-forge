# Getting Started

This tutorial walks you through installing `axm-smelt` and compacting your first payload.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
uv add axm-smelt
```

Or with pip:

```bash
pip install axm-smelt
```

## Step 1: Compact from the CLI

Pipe a JSON payload through `axm-smelt compact`:

```bash
echo '{"name": "Alice", "age": 30, "notes": null}' | axm-smelt compact
```

The compacted text is printed to stdout. Token savings are reported to stderr:

```
{"name":"Alice","age":30,"notes":null}
Tokens: 18 -> 12 (33.3% saved)
```

Use a preset for more aggressive compaction:

```bash
echo '{"name": "Alice", "age": 30, "notes": null}' | axm-smelt compact --preset moderate
```

```
{"name":"Alice","age":30}
Tokens: 18 -> 9 (50.0% saved)
```

## Step 2: Compact from Python

```python
from axm_smelt import smelt

data = '{\n  "name": "Alice",\n  "age": 30,\n  "notes": null\n}'
report = smelt(data, preset="moderate")

print(report.compacted)                    # {"name":"Alice","age":30}
print(f"{report.savings_pct:.1f}% saved") # 50.0% saved
print(report.strategies_applied)           # ['minify', 'drop_nulls']
```

## Step 3: Analyze Token Waste

Use `check` to see what each strategy would save, without modifying the input:

```bash
axm-smelt check --file data.json
```

```
Format: json
Tokens: 42
Strategies applied: none
Strategy estimates:
  minify: 18.2%
  drop_nulls: 9.5%
  flatten: 0.0%
```

## Step 4: Count Tokens

```bash
echo 'hello world' | axm-smelt count
# 2
```

```python
from axm_smelt import count

tokens = count("hello world")
print(tokens)  # 2
```

## Next Steps

- [Compact Data](../howto/compact.md) — Full CLI and API options
- [Use Strategies](../howto/strategies.md) — Apply individual strategies
- [Use Presets](../howto/presets.md) — Choose the right preset
- [Strategy Catalog](../explanation/strategies.md) — Detailed strategy reference
