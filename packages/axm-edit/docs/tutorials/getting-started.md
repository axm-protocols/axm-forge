# Edit and undo a temporary project

Learn the complete tool workflow: check, apply, inspect and undo. This tutorial
requires Python 3.12+ and creates its own disposable files.

## Install and inspect the interface

```bash
uv add axm-edit
axm batch_edit --help
axm batch_edit_check --help
```

The CLI comes from `axm`. The example below calls the same tool classes directly
so it can retain the structured checkpoint for rollback.

## Run the workflow

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from axm_edit.tools.batch_edit import BatchEditTool
from axm_edit.tools.batch_edit_check import BatchEditCheckTool
from axm_edit.tools.batch_rollback import BatchRollbackTool
from axm_edit.tools.read_file import ReadFileTool

with TemporaryDirectory() as directory:
    root = Path(directory)
    target = root / "settings.txt"
    target.write_text("mode = draft\n", encoding="utf-8")
    operations = [
        {"op": "replace", "file": "settings.txt", "edits": [
            {"old": "mode = draft", "new": "mode = ready"},
        ]},
        {"op": "create", "file": "notes/review.txt", "content": "Ready.\n"},
    ]

    check = BatchEditCheckTool().execute(path=directory, operations=operations)
    assert check.success, check.error
    assert not check.data["blocking"], check.data["diagnostics"]
    assert target.read_text() == "mode = draft\n"  # Check did not write.

    applied = BatchEditTool().execute(
        path=directory, operations=operations, lint=False,
    )
    assert applied.success, applied.error
    assert applied.data["summary"] == {"modified": 1, "created": 1, "deleted": 0}
    assert target.read_text() == "mode = ready\n"

    read = ReadFileTool().execute(path=directory, file="settings.txt")
    assert read.success, read.error
    print(read.data["content"])  # The content includes line-number prefixes.

    undone = BatchRollbackTool().execute(
        path=directory, checkpoint=applied.data["checkpoint"],
    )
    assert undone.success, undone.error
    assert target.read_text() == "mode = draft\n"
    assert not (root / "notes").exists()
```

The `old` value is the whole line, with no trailing newline. A substring such
as `draft` would not match that line in `batch_edit`.
`lint=False` keeps the tutorial independent of Ruff and project environments.

## Interpret the results

`check.success` says the check ran; `check.data["blocking"]` says whether
preflight found an error. Warnings make `ok=False` without necessarily blocking.
A nonblocking preflight is not a guarantee that engine validation or apply will
succeed.

The apply result's `checkpoint` is a JSON snapshot string, not a commit hash.
It is available here because Python receives structured `data`. Compact MCP
text omits it; do not invent a checkpoint from that text.

Next, learn [guarded full-file rewrites](../howto/rewrite.md),
[recovery limits](../howto/rollback.md), or
[tool dispatch through MCP and CLI](../howto/mcp.md).
