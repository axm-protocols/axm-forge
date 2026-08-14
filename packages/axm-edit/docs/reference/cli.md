# MCP Tools Reference

`axm-edit` ships no command-line binary. It exposes its functionality as **MCP
tools** registered under the `axm.tools` entry-point group, discovered by the
AXM MCP server. Each tool is an `AXMTool` whose `execute(**kwargs) -> ToolResult`
method is the single entry point.

## Tools

| Tool | Class | Purpose |
|---|---|---|
| `batch_edit` | `BatchEditTool` | Replace / rewrite / create / delete files in one atomic, validated batch (with `ruff --fix`). A blocking preflight refuses the batch before any write; the diagnostics come back under `data["preflight"]`. |
| `batch_rollback` | `BatchRollbackTool` | Restore the exact paths a batch touched from its `batch_edit` snapshot. |
| `read_file` | `ReadFileTool` | Read file content, optional line range, line-numbered output. |
| `write_file` | `WriteFileTool` | Write (create or overwrite) a single file. |
| `edit_file` | `EditFileTool` | Apply old/new edits to a single file. |
| `search_files` | `SearchFilesTool` | Grep-like search across project files (literal or regex). |
| `run_command` | `RunCommandTool` | Execute an **arbitrary** shell command with timeout (denylist is a best-effort guardrail, **not** a sandbox). |
| `list_dir` | `ListDirTool` | List files and directories with metadata. |
| `file_bytes` | `FileBytesTool` | Byte-level report on a file already on disk: sha256, size, literal non-ASCII vs textual escapes, divergence from an expected content. **Read-only** — it never writes. |

### `batch_edit` operations

`operations` accepts four `op` discriminators, in a single list:

| `op` | Required keys | Notes |
|---|---|---|
| `replace` | `file`, `edits` (each `old` / `new`, optional `line`) | Anchor-based; line numbers reference the **original** file |
| `create` | `file`, `content` | Fail-closed when the target already exists — there is **no** `overwrite` flag |
| `delete` | `file` | — |
| `rewrite` | `file`, `content`, `expected_checksum` | Whole-file replacement carrying the **exact** bytes (no anchor resolution, no quote normalisation, no re-indentation) — the safe path for a triple-quote-heavy module `replace` cannot address |

The rewrite digest is **mandatory**: it is the sha256 hex digest of the file
bytes as currently on disk. A stale digest is a hard refusal — a concurrent
modification is never silently clobbered — and there is no `overwrite` escape
hatch. `batch_edit_check` names that same key `checksum`; `batch_edit` accepts
either spelling and normalises it before the preflight runs. A rewritten `.py`
file joins the post-apply `ruff --fix` pass like any other touched file, and
the rendered summary lists it as `» {file} (rewrite)`.

## Python API

Auto-generated API reference is available under [Python API](api/axm_edit/index.md).
