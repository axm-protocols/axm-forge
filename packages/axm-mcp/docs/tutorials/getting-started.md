# Getting Started

The canonical setup lives in the **[Quick Start](quickstart.md)** — connect the
server to your MCP client in one command, verify the connection, and run your
first `verify`.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (provides `uvx`)

## Connect in one command

```bash
claude mcp add axm-mcp -- uvx --python 3.12 --from "axm-mcp[all]" axm-mcp
```

→ Full walkthrough, the `.mcp.json` form, and the advanced HTTP transport are in
the [Quick Start](quickstart.md).

## Next Steps

- [Quick Start](quickstart.md) — The canonical setup guide
- [CLI Reference](../reference/cli.md) — Full command documentation
- [Architecture](../explanation/architecture.md) — How the project is structured
