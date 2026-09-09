# Use the tools through MCP or CLI

Install `axm-edit` in the environment that runs `axm-mcp`, then restart
discovery as required by the server. A package installed in another virtual
environment is not automatically visible.
See [axm-mcp setup](https://forge.axm-protocols.io/mcp/).

## MCP façade

In façade mode, off-surface tools are still callable through `axm_call`.
The following is a JSON argument object for `axm_call`, not Python syntax:

```json
{
  "name": "batch_edit_check",
  "arguments": {
    "path": "/project",
    "operations": [
      {
        "op": "replace",
        "file": "settings.txt",
        "edits": [{"old": "mode = draft", "new": "mode = ready"}]
      }
    ]
  }
}
```

This assumes `/project/settings.txt` exists with the indicated line.
After checking the diagnostics, call `batch_edit` with those operations and
`lint: false` if you do not want Ruff to mutate Python files.
Only `batch_edit` declares `expose_directly=True` in this package; the server
controls which tools actually appear in a client's direct listing.

Read a file using a root and a relative target:

```json
{
  "name": "read_file",
  "arguments": {"path": "/project", "file": "settings.txt"}
}
```

`axm_call` returns compact text, so it omits the batch snapshot even though
the underlying tool produces it in `ToolResult.data`. To retain undo data,
use an interface that exposes structured results; see [rollback](rollback.md).

## Generic CLI

`axm` supplies the CLI wrapper for the same registered tools.
These commands inspect help and do not modify files:

```bash
axm batch_edit --help
axm batch_edit_check --help
axm write_file --help
axm run_command --help
```

For an existing project, a read returns either compact text or the structured
`data` object with `--json-output`:

```bash
axm read_file --path /project --file settings.txt --json-output
```

Batch operations use a JSON list:

```bash
axm batch_edit --path /project --no-lint --json-output \
  --operations '[{"op":"replace","file":"settings.txt","edits":[{"old":"mode = draft","new":"mode = ready"}]}]'
```

Retain that JSON output privately if you need the checkpoint; it contains
the original target-file bytes. A CLI exit code of zero reflects tool
execution success. For `batch_edit_check`, `file_bytes` and
`run_command`, inspect their own verdict fields too.
