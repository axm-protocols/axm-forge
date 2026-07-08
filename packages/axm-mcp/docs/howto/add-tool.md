# Add a New Tool

Expose your own Python tool as an MCP-callable function via `axm-mcp`.

## Prerequisites

Your tool must satisfy the `AXMTool` protocol from `axm.tools.base` — any class with a `name` property and an `execute()` method qualifies (no inheritance needed).

## Step 1: Create the Tool Class

```python
from axm.tools.base import ToolResult


class MyTool:
    @property
    def name(self) -> str:
        return "my_tool"

    def execute(self, *, path: str = ".") -> ToolResult:
        """Do something useful."""
        return ToolResult(success=True, data={"result": "ok"})
```

### Dual-format results

`execute()` returns a `ToolResult(success, data, text=None, error=None)`. The
wrapper treats the two payloads differently:

- **`data`** — the structured dict that programmatic callers (hooks, gates,
  DAG nodes) read.
- **`text`** — an optional pre-rendered string. On a **successful** result with
  `text` set, the wrapper short-circuits and returns the raw string (FastMCP
  renders it as `TextContent`), so the agent sees clean markdown instead of
  JSON. A **failing** result (or a raised exception) never short-circuits: it is
  flattened to `{success: False, error: ...}` so the failure signal always
  reaches the caller.

```python
return ToolResult(
    success=True,
    data={"score": 90, "issues": []},   # for hooks/gates
    text="my_tool: 90/100 (0 issues)",  # for the agent
)
```

Reserved keys in `data` (`success`, `error`, `hint`) are relocated to
`data_*` rather than clobbering the envelope.

### Facade discovery metadata (optional)

The facade reads three optional class attributes (via `tool_metadata`) — set
them so agents can *find* your tool through `axm_search`, and so a
frequently-used tool can bypass the facade:

```python
class MyTool:
    expose_directly = True          # register on the HOT PATH (its own tools/list
                                    # entry) instead of only behind axm_call
    domain = "quality"              # groups it under axm_capabilities
    tags = frozenset({"lint", "ci"})  # matched by axm_search's keyword search

    @property
    def name(self) -> str:
        return "my_tool"
    ...
```

- **`expose_directly`** (default `False`) — `True` registers the tool as an
  individual MCP tool (the hot path), so it shows up directly in `tools/list`.
  Reserve it for high-frequency tools; everything else stays compact behind the
  facade.
- **`domain`** — a short grouping key surfaced by `axm_capabilities`.
- **`tags`** — extra keywords `axm_search` matches against (name + summary +
  tags + domain).

## Step 2: Register as Entry Point

In your package's `pyproject.toml`:

```toml
[project.entry-points."axm.tools"]
my_tool = "my_package.tools:MyTool"
```

## Step 3: Install and Verify

```bash
uv pip install -e .
axm-mcp
```

Call `list_tools` — your tool should appear in the list (it always enumerates the full surface). To invoke it, use the facade: `axm_describe` for its contract, then `axm_call`.

## How Discovery Works

`axm-mcp` uses `importlib.metadata.entry_points(group="axm.tools")` at startup (`discover_tools()`). Each entry point is instantiated if it is a class, or used as-is if it is a plain dispatcher function. By default (`AXM_MCP_FACADE=1`) the discovered tools are then surfaced through the compact facade — reachable via `axm_search` / `axm_describe` / `axm_call` — unless they opt into the direct hot path with `expose_directly`. Set `AXM_MCP_FACADE=0` to register every discovered tool directly instead. Either way, no configuration is needed — just install the package.
