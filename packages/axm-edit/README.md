<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-edit — Validated batch file editing for AXM agents and Python callers</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-edit/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-edit/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-edit/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-edit/"><img src="https://img.shields.io/pypi/v/axm-edit" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io/edit/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

`batch_edit` replaces, creates, deletes and rewrites files in one request.
It validates before writing and snapshots the target paths for automatic
rollback on apply failure. Apply and recovery are best-effort filesystem
operations, not an OS transaction or a lock against concurrent writers.

## Features

- Whole-line replacement, file creation, deletion and checksum-guarded rewrite.
- Batch validation before writing and targeted snapshots for recovery.
- Read-only batch checks and file inspection, search and listing tools.
- Python API and registered tools for the unified AXM CLI and MCP server.

## Installation

```bash
uv add axm-edit
uv run axm batch_edit --help
```

Python 3.12+ is required. The dependency `axm` supplies the generic CLI;
there is no separate `axm-edit` executable. Install `axm-mcp` in the same
environment to expose the registered `axm.tools` to an MCP client.

## Quick Start

This self-contained Python example changes only a temporary directory.
The root API does not run the tool's preflight or post-edit Ruff pass.
Save it as `example.py` and run `uv run python example.py` after installation.

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from axm_edit import CreateOp, Edit, ReplaceOp, batch_apply, rollback

with TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "settings.txt").write_text("mode = draft\n", encoding="utf-8")
    result = batch_apply(root, [
        ReplaceOp(file="settings.txt", edits=[
            Edit(old="mode = draft", new="mode = ready"),
        ]),
        CreateOp(file="notes.txt", content="Ready for review.\n"),
    ])
    assert result.success, result.error
    assert result.summary == {"modified": 1, "created": 1, "deleted": 0}
    assert result.checkpoint is not None
    restored = rollback(root, result.checkpoint)
    assert restored.ok, restored.unrestored
    assert (root / "settings.txt").read_text() == "mode = draft\n"
    assert not (root / "notes.txt").exists()
```

The assertions verify that one file was changed and another created, then
that rollback restored their prior state. Success produces no output.

## Usage

### Choose an interface

| Need | Tool |
|---|---|
| Validate a proposed batch without writing | `batch_edit_check` |
| Apply whole-line edits and file operations | `batch_edit` |
| Undo using a retained structured snapshot | `batch_rollback` |
| Read, search or list project files | `read_file`, `search_files`, `list_dir` |
| Write a file or replace substrings | `write_file`, `edit_file` |
| Inspect SHA-256, UTF-8 and escape sequences | `file_bytes` |
| Run an executable in a selected directory | `run_command` |

`read_file`, `write_file` and `edit_file` take `path` (project root) and
`file` (target within it). `file_bytes` instead takes a file path without
project-root confinement. `run_command` constrains its initial working
directory, not the executable's filesystem or network access.

The tool `batch_edit` runs Ruff fix/format by default on touched Python files;
use `lint=False` / CLI `--no-lint` to apply only the supplied edits.
A successful tool result does not certify lint cleanliness.
The checkpoint is present in structured `data` after apply starts, but is
omitted from the compact text returned by the MCP `axm_call` façade.

## Documentation

- [Getting started](https://forge.axm-protocols.io/edit/tutorials/getting-started/)
- [Batch contracts](https://forge.axm-protocols.io/edit/reference/batch/)
- [Filesystem tools](https://forge.axm-protocols.io/edit/reference/filesystem/)
- [Rollback and concurrency limits](https://forge.axm-protocols.io/edit/howto/rollback/)
- [Python API](https://forge.axm-protocols.io/edit/reference/api/)

## Development

From the [axm-forge](https://github.com/axm-protocols/axm-forge) workspace root:

```bash
uv sync --all-packages --all-groups
uv run --package axm-edit --directory packages/axm-edit pytest
uv run --package axm-edit --directory packages/axm-edit --group docs mkdocs build --strict
```

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for the workspace workflow.
The MkDocs homepage is [docs/index.md](docs/index.md); this README is a separate
entry point.
## License

Licensed under Apache-2.0. See [LICENSE](LICENSE).
