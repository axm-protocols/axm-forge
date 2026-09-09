# Add a New Tool

Expose a request/response operation once, using an `axm.tools` entry point.
Use an AXMTool implementation with explicit typed keyword parameters so the
MCP schema, facade contract and AXM CLI can describe the same operation.

## 1. Implement the operation

Put this in `my_package/tools.py`:

```python
from __future__ import annotations

from axm.tools.base import ToolResult

__all__ = ["MyTool"]


class MyTool:
    domain = "example"
    tags = frozenset({"greeting"})
    expose_directly = False

    @property
    def name(self) -> str:
        return "my_tool"

    def execute(self, *, name: str = "world") -> ToolResult:
        """Return a greeting.

        Args:
            name: Person to greet.
        """
        greeting = f"Hello, {name}!"
        return ToolResult(
            success=True,
            data={"greeting": greeting},
            text=greeting,
        )
```

This satisfies the structural AXMTool protocol; inheritance is not required.
The class must be constructible without arguments for entry-point discovery.
Keep the entry-point name and `name` property consistent.

## 2. Publish the entry point

Add to your installable package's `pyproject.toml`:

```toml
[project.entry-points."axm.tools"]
my_tool = "my_package.tools:MyTool"
```

Declare `axm` in the package's dependencies. Install your package into the
server environment; for a dedicated virtual environment:

```bash
uv pip install --python /absolute/path/to/server-venv/bin/python -e /absolute/path/to/my-package
```

Restart that environment's server. Merely adding a Python file or installing
into another venv does not update its entry-point catalog.

## 3. Discover and invoke

Send these MCP `tools/call` parameter objects separately:

```json
{"name": "axm_describe", "arguments": {"name": "my_tool"}}
```

```json
{"name": "axm_call", "arguments": {"name": "my_tool", "arguments": {"name": "Ada"}}}
```

The result is `Hello, Ada!`. It is intentionally absent from the direct
MCP list because `expose_directly=False`; `list_tools` still enumerates it.

## Metadata and errors

`domain` groups capabilities, `tags` improves substring discovery, and
`expose_directly=True` gives a frequently used tool its own direct MCP
entry. There is no need for a second registration to keep facade access.

Programmatic AXMTool calls retain `data`. At the MCP boundary, a successful
`text` replaces that structured payload; failures with nonempty text retain
diagnostics with an error prefix when needed. See the
[result contract](../reference/facade.md#toolresult-at-the-mcp-boundary)
before building a consumer.

Return `ToolResult(success=False, error="...")` for a known failure.
Execution exceptions are flattened by the wrapper. Do not use reserved
envelope/data relocation keys for unrelated payload fields, and avoid
catch-all kwargs when explicit parameters can reject user mistakes.

For a mutating tool, documenting its effects and registering an entry point
does not automatically classify every payload for shared write enforcement.
Review the AXM write-scope decision layer and
[shared-policy limitations](../reference/shared-contracts.md).
