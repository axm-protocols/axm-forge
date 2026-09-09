# Use via MCP and DAG Nodes

Install `axm-smelt` in the environment used by the MCP server. Its
`axm.tools` entry points register `smelt`, `smelt_check`, and `smelt_count`.
A separate project environment does not automatically install tools into an
already running server.

## Call through the façade

With an existing asynchronous MCP client session named `session`, call the
AXM server's façade. This fragment assumes the session is already connected:

```python
result = await session.call_tool(
    "axm_call",
    arguments={
        "name": "smelt",
        "arguments": {
            "data": '{"name": "Alice", "notes": null}',
            "preset": "moderate",
        },
    },
)
```

In façade mode the individual tool need not appear as a directly exposed MCP
method. Search the catalog with `axm_search` and call it through `axm_call`.
The façade renders text; an MCP client's response is not itself a Python
`ToolResult`. The [underlying contracts](../reference/contracts.md#toolresult-data)
describe the fields available to Python/DAG integrations.

Prefer explicit `data` for remote calls. `input_path` is resolved on the
**server's filesystem**, not the client's machine; omitted/empty data can read
the server process's non-interactive stdin. Do not use stdin as a remote input
channel.

## Choose the tool

| Need | Tool |
|---|---|
| Compacted text plus actual pipeline metrics | `smelt` |
| Positive isolated strategy estimates | `smelt_check` |
| Count using a requested tiktoken model/encoding | `smelt_count` |

A successful call with zero savings is valid. Tools convert exceptions to
failure results. The Python `check` report has cumulative safe savings, but
the `smelt_check` tool exposes only format, count and isolated estimates.

## Wrap as a DAG node

```python
from axm import tool_node

compact = tool_node(
    "smelt",
    args={"data": "payload"},
    returns={"compact_text": "compacted", "saved_pct": "savings_pct"},
)
output = compact({"payload": '{"name": "Alice", "notes": null}'})
print(output["compact_text"])
```

Explicit `returns` chooses fields from the tool's data. A source value
`"text"` selects the human-readable rendering instead, including its header.
The node fails on a failed tool result; this prevents a file or tokenizer error
from being mistaken for an empty successful compaction.

## Keep sensitive content under caller control

Compaction is not redaction: the returned payload can still contain all
original secrets. `safe` makes no sensitive-data guarantee. Choose inputs and
destinations according to the application, and review
[preset trade-offs](presets.md) before injecting transformed context.
