# Use via MCP

`axm-smelt` exposes a `SmeltTool` via the `axm.tools` entry point group. AI agents can call it through [`axm-mcp`](https://github.com/axm-protocols/axm-forge/tree/main/packages/axm-mcp).

## Tool signature

```python
SmeltTool.execute(
    *,
    data: str | dict | list = "",         # Text or pre-parsed data to compact
    strategies: list[str] | None = None,  # Explicit strategy list
    preset: str | None = None,            # Named preset (safe/moderate/aggressive)
) -> ToolResult
```

Three tools are registered in the `axm.tools` entry point group: `smelt`
(compaction), `smelt_check` (analysis — what *would* be compacted and the
projected savings), and `smelt_count` (token count of an input, no compaction).
All arguments are keyword-only.

When `data` is a dict or list, it is passed directly to the pipeline via `parsed=`, avoiding a `json.dumps` → `json.loads` round-trip. String inputs follow the original path unchanged.

If neither `strategies` nor `preset` is given, the `safe` preset is used.

`SmeltCheckTool` follows the same pattern: when `data` is already structured, it is passed as `parsed=` to `check()`.

## Example agent call

```python
# Via axm-mcp
result = await mcp.call_tool("smelt", {
    "data": raw_json,
    "preset": "moderate",
})
```

## ToolResult fields

On success, `result.data` contains a JSON-serializable dict:

```json
{
  "compacted": "{\"name\":\"Alice\"}",
  "format": "json",
  "original_tokens": 14,
  "compacted_tokens": 9,
  "savings_pct": 35.7,
  "strategies_applied": ["minify"],
  "counter_backend": "tiktoken"
}
```

`counter_backend` reports which token counter produced the numbers. Today it is
always `tiktoken`: a Claude or otherwise unknown model name routes to the
`o200k_base` proxy encoding (an approximation, no `len // 4` heuristic and no
network call) rather than failing. It also appears in the text header so the
source of the counts is never silent. `smelt_count` exposes the same
`counter_backend` key in its `data` and text. The field is kept as the seam for
a future tokenizer backend (e.g. HuggingFace/SentencePiece). For an *exact*
Claude count, read `usage.input_tokens` from the run rather than this proxy.

On error, `result.success` is `False` and `result.error` contains the message.

## When to use which preset from an agent

- Use `safe` when passing data to tools that parse it back (e.g., API calls with JSON bodies)
- Use `moderate` for context injection where nulls and empty fields add no value
- Use `aggressive` for large retrieved documents where maximum context savings matter
