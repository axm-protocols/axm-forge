# Filesystem and process tools

Except `file_bytes`, file targets use `path` as an existing project root.
`read_file`, `write_file` and `edit_file` additionally require `file`.
Resolution refuses targets outside the root, including symlink escapes at
resolution time. Absolute paths inside the root may resolve successfully,
but relative `file` values are the intended interface.

This is a path barrier, not an OS sandbox or protection against concurrent
symlink swaps. The process tool and unconfined byte reader have different
boundaries, described below.

## read_file

Arguments: `path="."`, required `file`, optional `start_line` and
`end_line` (1-based, inclusive). Reads UTF-8 text, rejects detected binary
files, and returns `content` with line numbers, `file`, `total_lines`,
`truncated`, and `showing: {start, end, count}`.

Unbounded reads cap returned content at 2,000 lines; explicit ranges bypass
that default cap. The implementation reads the file before selecting lines,
so this is an output cap, not streaming I/O. Do not hash or write back numbered
`content` as if it were the original bytes.

## write_file

Arguments: `path="."`, required `file` and `content`.
Creates parents and writes UTF-8, overwriting an existing file.
Returns the resolved absolute `path` and UTF-8 `bytes` count.

There is no checksum, lint pass, checkpoint or atomic-replacement guarantee.
It uses a direct text write. Choose `batch_edit` when validation and recovery
across paths are needed.

## edit_file

Arguments: `path="."`, required `file`, `old`, `new`, and `count=1`.
Uses exact substring matching. No match fails; multiple matches with
`count=1` fail as ambiguous, even if `count=1` was explicitly supplied.
Use `count=-1` for all, or another positive integer to limit replacements.
Returns absolute `path`, `replacements` and the 1-based `first_line`.

This is a direct UTF-8 read/write without a batch snapshot, lint or protection
against another writer between read and write. It can normalize CRLF to LF.

## search_files

Arguments: `path="."`, required nonempty `pattern`, `is_regex=False`,
optional `include` list. Include globs match **basenames**, for example
`["*.md", "*.toml"]`, rather than directory-relative paths.
Invalid regex syntax fails.

Returns `matches` (`file`, 1-based `line`, `content`), `count` and
`truncated`. At most 50 matches are collected. Each content line is capped
at 500 characters with a truncation marker; use an actual read for anchors.
Directory and filename lists are sorted during traversal. There is no cursor
or pagination API to retrieve results beyond the cap.

Hidden directories and common build/cache directories are skipped, as are
detected binary files, unreadable/undecodable files and escaping symlinks.
This does not implement Git ignore rules and is not proof that a repository
contains no other occurrences.

## list_dir

Arguments: `path="."`, `max_depth=1`; values below 1 are clamped to 1.
Returns `entries` (`name`, relative `path`, `type`, `size_bytes`),
`count`, `truncated`. Directory size is null; unreadable file size can
also be null.

Entries are alphabetical within each visited directory; the traversal caps
at 200 entries. Hidden names, selected build artifacts and symlink escapes
are excluded. Permission-denied directories can be skipped. This is a bounded
view, not a complete filesystem inventory.

## file_bytes

Arguments: required file `path`, optional `expected`,
`expect_escaped=False`, `encoding="utf-8"` (the only supported encoding).
Unlike the other readers, it has no project-root parameter or confinement
barrier. Supply an absolute path to a file you intend to inspect.

Returns `sha256`, `size_bytes`, `encoding_ok`, bounded occurrence lists
and total counts, `mismatch`, `hint` and `verdict`:

- `ok`
- `mismatch`
- `literal_where_escaped_expected`
- `escaped_where_literal_expected`
- `decode_error`

The tool can succeed with any of these verdicts, including invalid UTF-8.
Read-only means no explicit write; filesystem access-time behavior is controlled
by the OS. The entire file is read into memory.

## run_command

Arguments: required `command`, `path="."`, optional `cwd` within the root,
`timeout=30` seconds.
The string is split with `shlex.split` and passed to `subprocess.run`
**without a shell**. Pipes, redirections, `&&`, wildcard expansion and
environment-variable expansion do not happen automatically.
An explicit shell executable can be invoked if intended.

The selected executable inherits the process environment and permissions.
Only the initial working directory is constrained; the process can access
other paths or the network. A substring denylist is a best-effort guardrail,
not a sandbox.

Returned data includes `stdout`, `stderr`, `exit_code`, `timed_out`
and `truncated`. Each stream is capped at 4,096 characters plus a marker.
A nonzero exit or timeout still returns `success=True`; timeout is reported
as `exit_code=-1`, `timed_out=True`. A missing executable or invalid
working directory is a tool failure.
