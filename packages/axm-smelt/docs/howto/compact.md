# Compact Data

Reduce token count through the Python API or the registered `smelt` AXMTool.

## AXMTool access

Compaction is registered once as the `smelt` AXMTool. That declaration powers
MCP, the AXM CLI, and DAG nodes; there is no standalone `axm-smelt compact`
command.

Redirect text to standard input or designate a UTF-8 file:

```bash
printf '{"name": "Alice", "notes": null}\n' | axm smelt
axm smelt --input-path ./payload.json
```

Pass `data`, `strategies`, and `preset` as tool inputs. Input is resolved in this
order: explicit data, `--input-path`, then non-interactive standard input. The
tool returns the compacted value and metrics in a structured `ToolResult`;
persisting that output remains the caller's responsibility. If the designated
path does not exist or is not valid UTF-8, the command exits with a non-zero
status and a diagnostic that names the path. See [Use via MCP](mcp.md) for a
complete programmatic example.

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
| `counter_backend` | `CounterBackend` | Token-counter backend used (always `tiktoken`; retained as the seam for a future tokenizer backend) |
