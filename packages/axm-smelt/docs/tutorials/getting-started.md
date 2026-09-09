# Getting Started

Compact a JSON payload, verify its meaning, and compare a more destructive
preset. You need Python 3.12+ and an environment containing `axm-smelt`.

## Install

From an existing uv project:

```bash
uv add axm-smelt
```

Run the Python snippets in that environment (for example `uv run python`).
With pip, install into an activated virtual environment:

```bash
pip install axm-smelt
```

## Step 1: Compact JSON and verify the result

```python
import json
from axm_smelt import smelt

data = """{
  "name": "Alice",
  "age": 30,
  "notes": null
}"""
report = smelt(data)
assert json.loads(report.compacted) == json.loads(data)
assert report.compacted_tokens <= report.original_tokens
print(report.compacted)
print(f"{report.savings_pct:.2f}% saved")
print(report.strategies_applied)
```

The default preset is `safe`. This example verifies JSON values, not original
bytes or key order. The name does not promise lossless XML/YAML/Markdown
compaction; [preset trade-offs](../howto/presets.md) explain the differences.

## Step 2: Measure alternatives

```python
from axm_smelt import check

analysis = check(data)
for strategy, savings in analysis.strategy_estimates.items():
    print(f"{strategy}: {savings:.2f}% in isolation")
assert analysis.compacted == data
assert analysis.savings_pct == report.savings_pct
```

Estimates are independent; do not sum them. The cumulative `savings_pct`
belongs to the safe pipeline.

## Step 3: Inspect a structural transform

```python
reduced = smelt(data, strategies=["minify", "drop_nulls"])
assert "notes" not in json.loads(reduced.compacted)
print(reduced.compacted)
```

Removing a null field changes the object. Decide whether that is acceptable
before sending it to a consumer. Neither call overwrites the source.

## Step 4: Count and use the CLI

```python
from axm_smelt import count

print(count("hello world"))
```

In your uv project:

```bash
printf '{"name": "Alice", "notes": null}\n' | uv run axm smelt --json-output
uv run axm smelt_check --help
uv run axm smelt_count --data 'hello world'
```

The plain CLI renders a header and payload; `--json-output` renders the data
mapping. Counts use a tiktoken encoding, not a full model-request billing
estimate.

## Next steps

- [Compact and save text](../howto/compact.md)
- [Choose strategies](../howto/strategies.md)
- [Use MCP or DAG nodes](../howto/mcp.md)
- [Consult the Python/tool contract](../reference/contracts.md)
