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
