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

Call `list_tools` — your tool should appear in the list.

## How Discovery Works

`axm-mcp` uses `importlib.metadata.entry_points(group="axm.tools")` at startup. It instantiates each entry point class and registers it as an MCP tool. No configuration needed — just install the package.
