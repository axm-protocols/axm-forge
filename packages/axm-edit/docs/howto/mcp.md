# Use via MCP

`axm-edit` exposes its functionality as MCP (Model Context Protocol) tools via `axm-mcp`. It ships no command-line binary — every tool is an `AXMTool` AI agents call directly without spawning subprocesses.

!!! info "Setup"
    These tools are served by `axm-mcp`. If you haven't connected the server yet,
    see the **[axm-mcp Quick Start](https://forge.axm-protocols.io/mcp/tutorials/quickstart/)** —
    one command connects the whole toolchain. No per-package install needed.

## Available Tools

| MCP Tool | Purpose |
|---|---|
| `batch_edit` | Replace / create / delete files in one atomic, validated batch (with `ruff --fix`) — the flagship tool |
| `batch_rollback` | Restore the exact paths a batch touched from its `batch_edit` snapshot |
| `read_file` | Read file content, optional line range, line-numbered output |
| `write_file` | Write (create or overwrite) a single file |
| `edit_file` | Apply old/new edits to a single file |
| `search_files` | Grep-like search across project files (literal or regex) |
| `run_command` | Execute an arbitrary shell command with timeout (denylist is best-effort, **not** a sandbox) |
| `list_dir` | List files and directories with metadata |

## Usage

!!! note "MCP dispatch"
    The examples below show the **logical API** — the parameters each tool takes.
    In practice, AI agents call these via MCP tool dispatch (e.g. `mcp_axm-mcp_batch_edit`),
    not direct Python imports.

`batch_edit` is the primary entry point: a single atomic call replaces what would otherwise be several sequential edits across files.

```json
batch_edit(path="/project", operations=[
    {"op": "replace", "file": "src/core.py", "edits": [{"old": "class OldName:", "new": "class NewName:"}]},
    {"op": "create",  "file": "src/utils.py", "content": "def helper():\n    return 42\n"},
    {"op": "delete",  "file": "src/obsolete.py"}
])
```

Every `batch_edit` returns a `checkpoint` snapshot payload; pass it back to undo the whole batch:

```
batch_rollback(path="/project", checkpoint="abc123def")
```

Read-only inspection mirrors the editing tools:

```
search_files(path="/project", pattern="deprecated_func", include=["*.py"])
read_file(path="/project/src/core.py")
```

## Entry Points

All tools are auto-discovered via the `axm.tools` entry-point group — see the
[MCP Tools Reference](../reference/cli.md) for the full tool / class mapping.
`axm-mcp` discovers these automatically at startup.
