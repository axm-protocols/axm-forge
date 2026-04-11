# Use via MCP

`axm-smelt` exposes a `SmeltTool` via the `axm.tools` entry point group. AI agents can call it through [`axm-mcp`](https://github.com/axm-protocols/axm-nexus/tree/main/packages/axm-mcp).

## Tool signature

```python
SmeltTool.execute(
    data: str | dict | list,              # Text or pre-parsed data to compact
    strategies: list[str] | None = None,  # Explicit strategy list
    preset: str | None = None,            # Named preset (safe/moderate/aggressive)
) -> ToolResult
```

When `data` is a dict or list, it is passed directly to the pipeline via `parsed=`, avoiding a `json.dumps` → `json.loads` round-trip. String inputs follow the original path unchanged.

If neither `strategies` nor `preset` is given, the `safe` preset is used.

`SmeltCheckTool` follows the same pattern: when `data` is already structured, it is passed as `parsed=` to `check()`.

## Example agent call

```python
# Via axm-mcp
result = await mcp.call_tool("smelt_compact", {
    "data": raw_json,
    "preset": "moderate",
})
```

## ToolResult fields

On success, `result.output` contains a JSON-serializable dict:

```json
{
  "compacted": "{\"name\":\"Alice\"}",
  "original_tokens": 14,
  "compacted_tokens": 9,
  "savings_pct": 35.7,
  "format": "json",
  "strategies_applied": ["minify"]
}
```

On error, `result.success` is `False` and `result.error` contains the message.

## When to use which preset from an agent

- Use `safe` when passing data to tools that parse it back (e.g., API calls with JSON bodies)
- Use `moderate` for context injection where nulls and empty fields add no value
- Use `aggressive` for large retrieved documents where maximum context savings matter
