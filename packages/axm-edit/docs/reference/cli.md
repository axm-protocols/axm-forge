# MCP Tools Reference

`axm-edit` ships no command-line binary. It exposes its functionality as **MCP
tools** registered under the `axm.tools` entry-point group, discovered by the
AXM MCP server. Each tool is an `AXMTool` whose `execute(**kwargs) -> ToolResult`
method is the single entry point.

## Tools

| Tool | Class | Purpose |
|---|---|---|
| `batch_edit` | `BatchEditTool` | Replace / create / delete files in one atomic, validated batch (with `ruff --fix`). |
| `batch_rollback` | `BatchRollbackTool` | Restore the exact paths a batch touched from its `batch_edit` snapshot. |
| `read_file` | `ReadFileTool` | Read file content, optional line range, line-numbered output. |
| `write_file` | `WriteFileTool` | Write (create or overwrite) a single file. |
| `edit_file` | `EditFileTool` | Apply old/new edits to a single file. |
| `search_files` | `SearchFilesTool` | Grep-like search across project files (literal or regex). |
| `run_command` | `RunCommandTool` | Execute an **arbitrary** shell command with timeout (denylist is a best-effort guardrail, **not** a sandbox). |
| `list_dir` | `ListDirTool` | List files and directories with metadata. |

## Python API

Auto-generated API reference is available under [Python API](api/axm_edit/index.md).
