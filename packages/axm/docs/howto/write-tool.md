# Write a tool

Implement a request with explicit typed parameters and a `ToolResult`.
`AXMTool` is a structural protocol: inheriting from it is optional.
Use a stable entry-point name such as `demo_count`.

## Implement the operation

In a Python package named `demo_tools`, put this in `src/demo_tools/count.py`:

```python
from __future__ import annotations

from axm import ToolResult

__all__ = ["CountTool"]


class CountTool:
    """Count the supplied labels."""

    @property
    def name(self) -> str:
        """Tool identifier."""
        return "demo_count"

    def execute(self, *, labels: list[str]) -> ToolResult:
        """Return the number of labels."""
        count = len(labels)
        return ToolResult(
            success=True,
            data={"count": count},
            text=f"{count} labels",
        )
```

Keep `execute` synchronous and explicit: its signature drives generated CLI
arguments. Put domain validation and computation here, so the Python and
generated entry points share the same behavior. Return
`ToolResult(success=False, error="...")` for a handled failure.

## Declare discovery metadata

Add to the package's existing `pyproject.toml` (merge with existing tables):

```toml
[project.entry-points."axm.tools"]
demo_count = "demo_tools.count:CountTool"
```

The package must depend on `axm` and include `demo_tools` in its build.
The target class must be instantiable without arguments. A ready instance can
also be registered. Match the entry-point key and the tool's `name`.

From that project's root, install it and use the generated command:

```bash
uv sync
uv run axm demo_count --help
uv run axm demo_count --labels '["alpha", "beta"]'
uv run axm demo_count --labels '["alpha", "beta"]' --json-output
```

Expected text: `2 labels`. Expected JSON data:

```json
{"count": 2}
```

Registration makes the tool discoverable by an installed `axm-mcp` server.
This package does not start that server. Installing or changing entry-point
metadata may require restarting a long-running consumer.

## Add optional discovery attributes

On the tool class, you may declare:

```python
# Class-body fragment for CountTool:
agent_hint = "Count labels; accepts a list of strings."
expose_directly = False
domain = "demo"
tags = frozenset({"count", "labels"})
```

These attributes do not affect whether the tool satisfies `AXMTool`.
`tool_metadata` resolves only `expose_directly`, `domain` and `tags`;
`agent_hint` is read separately by interested consumers. In facade mode,
`expose_directly=False` keeps the tool off the MCP hot path without removing it
from facade discovery. It does not hide the generated CLI command.

Continue with [tool-node composition](tool-node.md) and the
[SDK contract](../reference/python-api.md).
