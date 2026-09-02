# Analyze Token Waste

Use `check` to analyze a payload and see how much each strategy would save — without modifying the input.

## AXMTool

Analysis is exposed as the `smelt_check` AXMTool through MCP, the AXM CLI, and
DAG nodes:

Redirect text to standard input or designate a UTF-8 file:

```bash
printf '{"name": "Alice", "notes": null}\n' | axm smelt_check
axm smelt_check --input-path ./payload.json
```

You can also provide the payload as the tool's `data` input. Input is resolved
in this order: explicit data, `--input-path`, then non-interactive standard
input. Its `ToolResult` reports the detected format, token count, isolated
strategy estimates, and real cumulative savings. There is no standalone
`axm-smelt check` command or `--file` shim.

Only strategies with positive savings are included — strategies that would
produce no savings or increase tokens are filtered out.

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
