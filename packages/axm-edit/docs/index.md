# axm-edit

Edit several files in one validated batch, inspect the result, and retain a
snapshot when your application needs to undo it.

`axm-edit` provides text/file operations. It does not resolve Python symbols
or automatically update imports and callers: for structural moves and renames,
use [axm-anvil](https://forge.axm-protocols.io/anvil/).

## Start here

- [Tutorial: edit and undo a temporary project](tutorials/getting-started.md)
- [How-to guides](howto/index.md): MCP, guarded rewrites, rollback
- [CLI and tool registry](reference/cli.md)
- [Batch contracts](reference/batch.md) and [filesystem tools](reference/filesystem.md)
- [Python API](reference/api/index.md)
- [Architecture and guarantees](explanation/architecture.md)

## What a batch guarantees

A validation error rejects the batch before the engine writes any target.
If apply fails, the engine attempts to restore the captured paths automatically.
The filesystem is not transactional: other readers can see intermediate
states, concurrent writers are not locked, and recovery can fail.

The `batch_edit` tool adds preflight diagnostics and optional Ruff fix/format.
The lower-level `batch_apply` root export applies typed operations without
those extra steps. Use the tool for the complete agent-facing workflow.

## Access

```bash
uv add axm-edit
axm batch_edit --help
axm write_file --help
```

The generic `axm` CLI discovers this package's `axm.tools` entry points.
An MCP server must have the package installed in its own environment.
The README is the repository entry point; this page is the MkDocs homepage.
