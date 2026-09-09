# Architecture and guarantees

## Layers

`axm-edit` separates typed file operations, filesystem execution and tool
presentation:

| Layer | Responsibility |
|---|---|
| Root exports / `models.operations` | Typed operations and result models |
| `core.precheck`, `precheck_fs`, `preflight` | Tool payload diagnostics and severity partition |
| `core.engine` | Resolve anchors, validate operations, snapshot and apply |
| `core.checkpoint` | Capture original bytes and restore recorded paths |
| `core.atomic_write` | Per-file whole-file rewrite replacement |
| `tools.batch_edit` | Preflight, engine orchestration, post-edit Ruff and ToolResult |
| Other `tools` modules | Read/write/search/list/process interfaces |

The root `batch_apply` function is a lower-level typed API. It does not run
the tool's preflight contract checks or post-edit Ruff. Tool classes are
registered through `axm.tools`, so MCP and the generic CLI share execution.

## Validate, then apply

The tool runs the shared preflight rules over authored dictionaries.
Errors block before parsing and snapshotting; warnings are returned but do
not block that phase. The engine then resolves and validates the operation set.
Preflight is not a complete simulation: engine validation can reject a
nonblocking check result.

For each replace, line hints and content anchors locate whole lines. Resolution
tries exact content and normalization fallbacks; indentation-normalized matches
are reindented when written. Resolved edits are spliced bottom to top so line
shifts do not invalidate earlier line numbers. Overlap is rejected.
Near-miss reports render tabs, spaces, nonbreaking spaces and newlines explicitly.

After validation, the engine snapshots resolved target paths, applies replaces,
then creates/deletes, then rewrites. Operations are grouped by kind rather than
executed as a sequential script in input order.

## Atomicity has two different scopes

**Batch validation** rejects before target writes. **Batch apply** performs
ordinary filesystem calls and attempts rollback on any apply exception.
There is no multi-file filesystem transaction. Another process can observe a
partially applied batch, and a crash can interrupt apply before Python recovers.

Replace/create use direct writes, delete uses unlink. Rewrite alone uses a
temporary sibling and `os.replace`, preserving permission bits and attempting
syncing. A concurrent reader of that file sees a replacement rather than a
partially written rewrite, but this does not make the surrounding batch atomic.

Rollback restores recorded bytes, not all metadata, and can fail. Root
`BatchResult.rollback_failed` reports incomplete automatic recovery; the
tool currently omits that field from structured data.
See [rollback](../howto/rollback.md) for consequences.

## Concurrent writers

The engine rechecks replace anchors against the content read for apply. This
detects some drift, not every race: another write can still occur after that
read. Rewrite checksums are checked during validation, not at the final
`os.replace`. Create/delete and path resolution are also not protected by locks.

Checkpoint recovery has no output checksum and can overwrite subsequent
changes to a snapshotted path. Use one writer per project or external
coordination. Neither the word “atomic” nor a successful preflight substitutes
for that coordination.

## Encoding and exactness

Operations accept text. Replace matches UTF-8 with universal-newline reads,
then preserves the detected LF/CRLF style on write. Create writes the supplied
text; rewrite encodes it as UTF-8 without anchor processing. Binary replace
targets and undecodable replace content are rejected during validation;
rewrite validation rejects detected binary targets.

Post-edit Ruff may change Python content after successful apply. Its errors
and warnings are informational fields rather than an engine rollback trigger.
The diff display is advisory and can miss formatting-only changes.
Use `lint=False` and inspect bytes when exact output is required.

## Path boundaries and resources

Root-relative tools resolve paths and refuse escapes. This does not lock
symlinks against concurrent changes. `file_bytes` is an unconfined file reader;
`run_command` only restricts its initial working directory and runs an
executable with inherited permissions.

Checkpoints contain complete base64 file contents. File reads and subprocess
capture also buffer data before output truncation. The tools' display caps
control returned content, not total memory use or a security boundary.
