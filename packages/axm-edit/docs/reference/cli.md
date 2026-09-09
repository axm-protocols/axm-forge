# CLI and tool registry

`axm-edit` declares tools under `axm.tools`; it has no dedicated executable.
The dependency `axm` discovers the same tools for `axm <tool>`.
The MCP server discovers installed entry points in its own environment.

## Registered tools

| Tool | Class (under `axm_edit.tools`) | Contract |
|---|---|---|
| `batch_edit` | `batch_edit.BatchEditTool` | [Apply a batch](batch.md) |
| `batch_edit_check` | `batch_edit_check.BatchEditCheckTool` | [Read-only preflight](batch.md#preflight-result) |
| `batch_rollback` | `batch_rollback.BatchRollbackTool` | [Restore a snapshot](../howto/rollback.md) |
| `read_file` | `read_file.ReadFileTool` | [Read text](filesystem.md#read_file) |
| `write_file` | `write_file.WriteFileTool` | [Write text](filesystem.md#write_file) |
| `edit_file` | `edit_file.EditFileTool` | [Replace substrings](filesystem.md#edit_file) |
| `search_files` | `search_files.SearchFilesTool` | [Search text](filesystem.md#search_files) |
| `list_dir` | `list_dir.ListDirTool` | [List paths](filesystem.md#list_dir) |
| `file_bytes` | `file_bytes.FileBytesTool` | [Inspect bytes](filesystem.md#file_bytes) |
| `run_command` | `run_command.RunCommandTool` | [Execute a process](filesystem.md#run_command) |

These are tool entry points, not root Python exports. Import a class from its
listed module when writing an integration. The complete signatures and root
library exports are in [Python API](api/index.md).

## Command conventions

```bash
axm batch_edit --help
axm read_file --path /project --file notes.txt --json-output
```

Python underscores in option names become hyphens, for example
`start_line` → `--start-line`, `lint_diff` → `--lint-diff`.
Use `--no-lint` to disable the batch tool's post-edit Ruff phase.
The generic wrapper adds `--json-output` to print the ToolResult's `data`
object, rather than its compact text. It omits the `success` envelope field;
failures are reported through stderr and a nonzero CLI exit. Examples with `/project` require your own existing
directory; the [tutorial](../tutorials/getting-started.md) creates a fixture.

## Success is not always the domain verdict

| Tool | Fields to inspect after execution succeeds |
|---|---|
| `batch_edit_check` | `blocking`, `error_count`, `warning_count`; `ok` is false for any diagnostic |
| `batch_edit` | `lint_errors`, `warnings`, and final files; lint is not a success gate |
| `file_bytes` | `verdict` and `encoding_ok` |
| `run_command` | `exit_code` and `timed_out` |

For these tools, the CLI process can exit zero even when the domain outcome
requires action. A nonzero command launched by `run_command` is one example.
