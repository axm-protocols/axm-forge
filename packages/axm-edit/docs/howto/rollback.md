# Undo a batch and handle failures

## Retain a successful batch's checkpoint

A checkpoint is the complete JSON snapshot in `ToolResult.data["checkpoint"]`.
It contains base64-encoded pre-edit bytes and records paths that did not exist.
Store it unchanged, with the project root it belongs to. Base64 is not
encryption; treat a snapshot like the source files it contains.

The [tutorial](../tutorials/getting-started.md) demonstrates capturing and
returning this value to `BatchRollbackTool`. Its arguments are `path` and
`checkpoint`. On success its data is `{"restored": true}`; on failure it
returns `success=False` and a generic error.

The current generic CLI cannot bind this tool's `path` and `checkpoint`:
its `execute(**kwargs)` signature exposes no named parameters, so
`axm batch_rollback --help` lists only `--json-output`. Use the Python class
or an MCP call with the actual retained checkpoint instead. CLI
`batch_edit --json-output` can provide that checkpoint in its data object.

The compact text produced by `batch_edit` deliberately omits the payload.
An MCP client using only `axm_call` cannot recover it from that text.
Plan recovery before editing: retain structured results or use a dedicated,
clean Git worktree with a known baseline. Review the specific paths before any
Git restore; restoring the entire checkout can discard unrelated work.

## What is restored

Rollback restores the bytes of the snapshotted paths, recreates deleted files,
removes files that were absent before the batch, and removes newly created
directories only when empty. Unrelated paths are not listed in the snapshot
and are not restored. Git history and the staging area are not changed.

A snapshot is not a full filesystem backup: it does not capture ownership,
permissions, timestamps, ACLs or extended attributes. A deleted executable
recreated from bytes may have different permission bits.

Rollback has no check that a target still contains the batch output.
It can overwrite a later edit to the same path. Serialize edits and undo
operations; never apply an old checkpoint blindly to ongoing work.

## Failure during apply

An engine validation failure happens before checkpoint creation and writes.
An exception during apply triggers automatic rollback. The root
`BatchResult` returns `success=False` and `rollback_failed=True` when
recovery is incomplete. Inspect the actual paths before retrying.

The `batch_edit` tool currently does **not** copy `rollback_failed` into
its structured `data`; its text/error is not sufficient proof that recovery
finished. Callers requiring that flag can use the root
[Python API](../reference/api/index.md). The root `rollback` function
returns per-path `restored` / `unrestored` lists and an `ok` property.

Rollback itself is best-effort, not atomic. For valid snapshots, filesystem
errors are collected per path. Only return checkpoints created by the engine:
the JSON format is not a validated interchange format for arbitrary input
or a portable backup API.

## Lint is a separate phase

Post-apply Ruff fix/format runs after the engine returns. Remaining diagnostics
or missing Ruff do not undo a successful batch. Check `data["lint_errors"]`,
`data["warnings"]` and the files themselves. The checkpoint still contains
the pre-batch state of the original targets.
