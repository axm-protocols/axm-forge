# Getting Started

This tutorial walks you through installing `axm-smelt` and compacting your first
payload through its stable Python API.

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

## Step 1: Compact from Python

```python
from axm_smelt import smelt

data = """{
  "name": "Alice",
  "age": 30,
  "notes": null
}"""
report = smelt(data, preset="moderate")

print(report.compacted)
print(f"{report.savings_pct:.1f}% saved")
print(report.strategies_applied)
```

The report carries both the compacted value and the measured token counts, so
callers can decide whether to keep the transformation.

## Step 2: Analyze token waste

Use `check` to estimate each strategy without modifying the input:

```python
from axm_smelt import check

report = check(data)
for strategy, savings in report.strategy_estimates.items():
    print(f"{strategy}: {savings:.1f}%")
```

## Step 3: Count tokens

```python
from axm_smelt import count

tokens = count("hello world")
print(tokens)
```

## Step 4: Discover the AXMTool surfaces

The package registers `smelt`, `smelt_check`, and `smelt_count` once under
`axm.tools`. That registry provides MCP, AXM CLI, and DAG-node access without
a separate `axm-smelt` executable:

```bash
axm smelt --help
axm smelt_check --help
axm smelt_count --help
```

For structured agent calls, continue with [Use via MCP](../howto/mcp.md).

## Next Steps

- [Compact Data](../howto/compact.md) — Python API and AXMTool access
- [Use Strategies](../howto/strategies.md) — Apply individual strategies
- [Use Presets](../howto/presets.md) — Choose the right preset
- [Strategy Catalog](../explanation/strategies.md) — Detailed strategy reference
