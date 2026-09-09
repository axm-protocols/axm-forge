# Use a tool as a node

`tool_node` builds a callable `payload -> dict` around an installed
`axm.tools` entry point. It does not start a scheduler or depend on loom.

## Declare inputs and writes

This self-contained example uses a local substitute, so it requires no provider
installation and performs no external I/O:

```python
from axm import ToolResult, tool_node
from axm.tools import override_tools


class CountTool:
    @property
    def name(self) -> str:
        return "demo_count"

    def execute(self, *, labels: list[str]) -> ToolResult:
        return ToolResult(
            success=True, data={"count": len(labels)}, text="Count complete"
        )


count_node = tool_node(
    "demo_count",
    args={"labels": "items"},
    returns={"total": "count", "summary": "text"},
)

with override_tools({"demo_count": CountTool()}):
    output = count_node({"items": ["alpha", "beta"]})

assert output == {"total": 2, "summary": "Count complete"}
```

`args` maps **execute parameter → payload key**.
`returns` maps **output key → result.data key**, except the reserved source
`"text"`, which always selects `ToolResult.text`.

Pass only the intended input slice: other payload keys are forwarded to
`execute`, not silently filtered by its signature. An unexpected keyword can
therefore cause `ToolNodeError`. Omitting `returns` produces an empty output
mapping even though the tool still executes.

## Understand errors

| Condition | Behavior |
|---|---|
| Entry point not found | `ToolNodeError` when the node runs |
| `execute` raises `TypeError` | Wrapped as `ToolNodeError` with the original cause |
| `success=False` | `ToolNodeError` by default |
| A declared data source is absent | `ToolNodeError` |
| `returns={"summary": "text"}` and text is absent | `{"summary": None}` |
| Other exception from `execute` | Propagates unchanged |

The source `"text"` never selects `data["text"]`, even if that key exists.
Rename such data upstream or use a dedicated adapter.

## Keep measured failures as data

Set `allow_failure_data=True` only when a failure is the domain observation
you intend to process, such as measured failed tests. The adapter then shapes
the declared data despite `success=False`. It does not add a success flag
automatically and still rejects missing declared data. Declare the evidence
keys you need; an empty `returns` mapping cannot establish evidence.

## Substitute tools without changing discovery

`override_tools` and `load_tool` are available from `axm.tools`, not from
the package root. Overrides apply both to nodes and to direct
`load_tool(name)` resolution. Nested blocks merge overrides and restore the
previous context on exit.

The scope uses `ContextVar`: tasks and `asyncio.to_thread` calls started in
that context inherit it. Independently started contexts do not.
A substitute overrides even an already-cached node tool and is never added to
that cache. Without an override, a node resolves and caches its tool lazily on
first invocation; direct `load_tool` resolution instantiates on each call.

See [SDK reference](../reference/python-api.md#tool-nodes) for signatures.
