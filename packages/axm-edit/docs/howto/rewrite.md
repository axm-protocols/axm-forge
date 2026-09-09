# Rewrite a whole file with a checksum

Use `rewrite` when line anchors are unsuitable, for example a whole Markdown
page or a Python module containing triple-quoted strings.

## Read the bytes, then submit their digest

```python
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from axm_edit.tools.batch_edit import BatchEditTool
from axm_edit.tools.batch_edit_check import BatchEditCheckTool

with TemporaryDirectory() as directory:
    target = Path(directory) / "notes.md"
    target.write_text("Draft.\n", encoding="utf-8")
    original = target.read_bytes()
    operations = [{
        "op": "rewrite",
        "file": "notes.md",
        "content": "# Ready\n\nReviewed.\n",
        "checksum": sha256(original).hexdigest(),
    }]
    checked = BatchEditCheckTool().execute(path=directory, operations=operations)
    assert checked.success and not checked.data["blocking"]
    result = BatchEditTool().execute(
        path=directory, operations=operations, lint=False,
    )
    assert result.success, result.error
    assert result.data["summary"]["rewritten"] == 1
    assert target.read_bytes() == b"# Ready\n\nReviewed.\n"
```

`file_bytes` also returns the SHA-256 digest of bytes on disk. Do not hash the
line-numbered output of `read_file`.

Use `checksum` in wire payloads shared with `batch_edit_check`.
`batch_edit` additionally accepts `expected_checksum` and normalizes it;
the check tool does not perform that normalization. Do not send both keys.
The Python `RewriteOp` model uses `expected_checksum` and is imported from
`axm_edit.models.operations`, not the root package.

## Refusals and guarantees

A missing target, symlink target, directory, stale checksum or an extra rewrite
key is refused. Engine validation additionally rejects binary targets.
Content is a Unicode string encoded as UTF-8, not arbitrary binary bytes.
No anchor normalization or reindentation runs. With default `lint=True`,
Ruff may subsequently change a rewritten Python file.

A rewrite uses a temporary sibling plus `os.replace`, preserves the target's
permission bits and attempts file/directory syncing. That atomic replacement
is per file; the whole batch is not a single filesystem transaction.

The checksum is checked in preflight and engine validation, **not immediately
before the final replacement**. There is no lock or compare-and-swap operation.
Serialize writers externally when concurrent edits are possible: a writer
in the validation-to-write interval can still be overwritten.
