# Quick Start

This tutorial walks you through installing `axm-mcp` and running it as an MCP server.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Installation

```bash
uv pip install axm-mcp
```

To include all AXM tools:

```bash
uv pip install "axm-mcp[all]"
```

## Step 1: Start the Server

```bash
axm-mcp
```

The server starts and auto-discovers all installed `axm.tools` entry points.

## Step 2: List Available Tools

From any MCP client, call the `list_tools` meta-tool:

```json
{"name": "list_tools"}
```

This returns all discovered tools with names and descriptions.

## Step 3: Run Verify

The `verify` tool checks any project in one shot:

```json
{"name": "verify", "arguments": {"path": "/path/to/project"}}
```

Returns audit score, governance score, and AST-enriched failure context.

## Next Steps

- [Add a new tool](../howto/add-tool.md) — Expose your own tool via MCP
- [Use the verify tool](../howto/verify.md) — Details on verify output
- [Architecture](../explanation/architecture.md) — How discovery works
