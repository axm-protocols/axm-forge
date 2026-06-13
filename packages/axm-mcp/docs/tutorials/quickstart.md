# Quick Start

This is the **canonical setup guide** for connecting the AXM MCP server to an
MCP client (Claude Code, IDE extensions, etc.). Every other "Use via MCP" page
links here — you don't need to repeat these steps anywhere else.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (provides `uvx`)

No manual install step is required: `uvx` downloads and runs the server on
demand, always resolving the latest published version.

## Step 1: Connect the server

The fastest path — one command, no JSON to edit:

```bash
claude mcp add --scope user axm-mcp -- uvx --python 3.12 --from "axm-mcp[all]@latest" axm-mcp
```

!!! note "What does `--scope user` do?"
    `--scope user` installs it globally (available in every session). Drop it to
    enable AXM per-project instead — the server then loads only in the directory
    where you run the command.

Prefer editing config by hand? Add this to your `.mcp.json` instead:

```json
{
  "mcpServers": {
    "axm-mcp": {
      "command": "uvx",
      "args": ["--python", "3.12", "--from", "axm-mcp[all]@latest", "axm-mcp"]
    }
  }
}
```

The file lives at `~/.claude.json` (global, all projects) or `.mcp.json` at a
project root (project-scoped — takes precedence when present). Restart your MCP
client after editing it.

!!! warning "Why `--from \"axm-mcp[all]\"` and not just `axm-mcp`?"
    The bare `axm-mcp` package is only the server shell. The actual tools
    (`audit`, `ast_*`, `git_commit`, `batch_edit`, …) ship in sibling packages
    that the server discovers through `axm.tools` entry points. The `[all]`
    extra pulls them in — without it you get a working server with almost no
    tools. `--python 3.12` pins the interpreter so resolution never falls back
    to an older Python that can't satisfy the dependency set.

## Step 2: Verify the connection

From your MCP client, call the built-in `list_tools` meta-tool:

```json
{"name": "list_tools"}
```

You should see `verify`, `audit`, `ast_*`, `init_*`, `bib_*`, and the rest of
the discovered tools. If the list is nearly empty, you almost certainly dropped
the `[all]` extra — revisit Step 1.

## Step 3: Run verify

The `verify` tool checks any project in one shot:

```json
{"name": "verify", "arguments": {"path": "/path/to/project"}}
```

Returns audit score, governance score, and AST-enriched failure context.

## Going further: persistent HTTP server (advanced)

The setup above uses **stdio** — the client launches one server process per
conversation. That's the simplest mode and works everywhere. If you run many
conversations and want a single shared process (warm AST cache, persistent
sessions, no per-conversation startup), migrate to the persistent HTTP
transport — see [Migrate to HTTP Transport](../howto/migration-http.md).

## Next Steps

- [Add a new tool](../howto/add-tool.md) — Expose your own tool via MCP
- [Verify a project](../howto/verify.md) — Details on verify output
- [Architecture](../explanation/architecture.md) — How discovery works
