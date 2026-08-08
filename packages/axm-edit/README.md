# axm-edit

**Atomic batch file editing for AI agents.**

<p align="center">
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-edit/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-edit/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-edit/coverage.json" alt="Coverage"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
</p>

---

## Overview

IDE agents edit files one-at-a-time. A refactor touching 30 files = 30 tool calls.
The agent spends 70% of its budget on mechanics.

**`axm-edit` replaces all of that with 1 call.**

## Features

- 🔧 **`batch_edit`** — Replace, create, and delete files in a single atomic operation
- 🧪 **`batch_edit_check`** — Read-only preflight of a batch: diagnostics without touching the disk
- 🔬 **`file_bytes`** — Read-only byte-level report on a file: sha256, literal non-ASCII vs textual escape sequences
- 📖 **`read_file`** — Read file content with optional line-range support
- 🔍 **`search_files`** — Grep-like search across project files (literal or regex)
- 📂 **`list_dir`** — List files and directories with metadata (recursive, depth-limited)
- ✏️ **`write_file`** — Write or overwrite file content
- 🖊️ **`edit_file`** — Find-and-replace (substring) in a single file
- ▶️ **`run_command`** — Execute shell commands with timeout and output truncation
- ⏪ **`batch_rollback`** — Restore the exact paths a batch touched from a targeted snapshot
- 🛡️ **Atomic** — All-or-nothing: validation runs before any file is touched
- 📐 **Bottom-to-top** — Line edits applied in reverse order to avoid line-shift problems
- 🔒 **Safe** — Path traversal blocked, `old` content validated, targeted path snapshot before writes

## Installation

```bash
uv add axm-edit
```

Or as a workspace dependency in `pyproject.toml`:

```toml
[project]
dependencies = ["axm-edit"]

[tool.uv.sources]
axm-edit = { workspace = true }
```

## Quick Start

```python
from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import Edit, ReplaceOp, CreateOp
from pathlib import Path

result = batch_apply(
    root=Path("/my/project"),
    operations=[
        ReplaceOp(file="src/core.py", edits=[
            Edit(line=5, old="class OldName:", new="class NewName:"),
        ]),
        CreateOp(file="src/new.py", content='"""New module."""\n'),
    ],
)
print(result.summary)  # {"modified": 1, "created": 1, "deleted": 0}
```

## MCP Tools

### `batch_edit`

Atomic batch file operations.

| Param | Type | Default | Description |
|---|---|---|---|
| `path` | `str` | `"."` | Project root directory |
| `operations` | `list[Op]` | — | List of replace/create/delete operations |
| `lint` | `bool` | `True` | Run `ruff --fix` on changed Python files after apply |
| `lint_diff` | `bool` | `True` | Surface per-file `lint_diffs` hunks of post-lint mutations |
| `lint_diff_max_ratio` | `float` | `0.5` | Fallback to `file_reread_recommended` when `len(diff) > ratio * len(post)` |

When `lint_diff=True` and ruff/harness_fix mutates any Python file, `ToolResult.data["lint_diffs"]` lists one entry per file: `{"file", "rules": [ruff codes], "diff": "@L<n>\n-old\n+new..."}`. On large rewrites the entry drops `diff` and carries `"diff_skipped": "file_reread_recommended"`.

**3 operation types:**

#### `replace` — modify lines in an existing file

```json
{
    "op": "replace",
    "file": "src/foo.py",
    "edits": [
        {"line": 3,  "old": "import bar",  "new": "import baz"},
        {"line": 17, "old": "x = bar()",   "new": "x = baz()"}
    ]
}
```

All line numbers reference the **original** file. The engine sorts edits bottom-to-top.

#### `create` — create a new file

```json
{"op": "create", "file": "src/new.py", "content": "\"\"\"New module.\"\"\"\n"}
```

Fails if file exists (unless `"overwrite": true`).

#### `delete` — remove a file

```json
{"op": "delete", "file": "src/old.py"}
```

### `batch_edit_check`

Read-only preflight of a `batch_edit` operation set. It runs the same validation
rules as `batch_edit` (broken `old` anchors, `create` on an existing file,
unknown edit keys, path traversal) and reports what would go wrong — **read-only**:
no disk write is ever performed, not a single file is created, modified or deleted.

| Param | Type | Default | Description |
|---|---|---|---|
| `path` | `str` | `"."` | Project root the batch would be applied to |
| `operations` | `list[Op]` | — | Same operation list as `batch_edit` |

```json
{
    "path": "/my/project",
    "operations": [
        {
            "op": "replace",
            "file": "src/foo.py",
            "edits": [{"line": 3, "old": "import bar", "new": "import baz"}]
        },
        {"op": "create", "file": "src/new.py", "content": "x = 1\n"}
    ]
}
```

Returns `data["ok"]` (`true` when nothing is wrong) and `data["diagnostics"]`,
one entry per problem found. Since nothing is written, it is safe to call it as
often as needed before committing to a real `batch_edit`.

### `file_bytes`

Byte-exact report on a file **already written to disk** — **read-only**: the
file is opened once in binary mode, no disk write is ever performed and no
metadata is changed. `path` is the **absolute** path to the file.

| Param | Type | Default | Description |
|---|---|---|---|
| `path` | `str` | — | Absolute path to the file to inspect |
| `expected` | `str?` | `None` | Content the caller believes it wrote |
| `expect_escaped` | `bool` | `False` | Whether escape sequences are expected verbatim on disk |
| `encoding` | `str` | `"utf-8"` | Decoding used for the report (only `utf-8`) |

Returns `data["verdict"]` — one of `ok`, `mismatch`,
`literal_where_escaped_expected`, `escaped_where_literal_expected`,
`decode_error` — plus `data["sha256"]`, `data["size_bytes"]`, the bounded
occurrence lists with their `*_total` counters, `data["mismatch"]` (offset and
ASCII-only reprs of the first divergence) and an actionable `data["hint"]`.
Undecodable bytes are a diagnostic (`encoding_ok: false`), not an error.

### `read_file`

Read file content with optional line-range support.

| Param | Type | Description |
|---|---|---|
| `path` | `str` | Project root directory |
| `file` | `str` | Relative path to the file |
| `start_line` | `int?` | Optional 1-indexed start line (inclusive) |
| `end_line` | `int?` | Optional 1-indexed end line (inclusive) |

### `search_files`

Grep-like search across project files.

| Param | Type | Description |
|---|---|---|
| `path` | `str` | Project root directory |
| `pattern` | `str` | Search string or regex (required) |
| `is_regex` | `bool?` | Treat pattern as regex (default `false`) |
| `include` | `list[str]?` | Glob patterns to filter files (e.g. `["*.py"]`) |

### `list_dir`

List files and directories with metadata.

| Param | Type | Description |
|---|---|---|
| `path` | `str` | Root directory to list (default `"."`) |
| `max_depth` | `int?` | Recursion depth — 1 for immediate children only (default `1`) |

### `run_command`

Execute shell commands with timeout and output truncation.

| Param | Type | Description |
|---|---|---|
| `path` | `str` | Project root directory |
| `command` | `str` | Shell command string (required) |
| `cwd` | `str?` | Working directory, relative to root |
| `timeout` | `int?` | Timeout in seconds (default 30) |

### `write_file`

Write (create or overwrite) a single file. `path` is the **absolute** path
to the file (not a project root); parent directories are created as needed.

| Param | Type | Description |
|---|---|---|
| `path` | `str` | Absolute path to the file to write |
| `content` | `str` | Text content to write |

### `edit_file`

Find-and-replace in a single file. Unlike `batch_edit` (whole-line `old`),
`edit_file` matches `old`/`new` as **substrings**. `path` is the **absolute**
path to the file.

| Param | Type | Description |
|---|---|---|
| `path` | `str` | Absolute path to the file to edit |
| `old` | `str` | Text to find (exact substring match) |
| `new` | `str` | Replacement text |
| `count` | `int?` | Max replacements — `-1` for all, else a positive integer (default `1`) |

> **Note** — `write_file` and `edit_file` take an **absolute file path** and are
> not confined to a project root, unlike the root-relative tools (`read_file`,
> `search_files`, `list_dir`, `run_command`, `batch_edit`). Like `run_command`,
> they are not a sandbox: only point them at paths you intend to write.

### `batch_rollback`

Restore the exact paths a batch touched from its snapshot.

| Param | Type | Description |
|---|---|---|
| `path` | `str` | Project root directory |
| `checkpoint` | `str` | Snapshot payload (JSON string) from the `batch_edit` response — pass it back verbatim, it is not a short hash |

## Development

This package is part of the **axm-forge** workspace.

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-groups

# Run tests for this package
uv run pytest --package axm-edit
```

📖 **[Full documentation](https://forge.axm-protocols.io/edit/)**

## License

Apache-2.0 — © 2026 Gabriel Jarry
