# How-To Guides

Task-oriented recipes for common `axm-edit` workflows.

## Cross-codebase rename

Rename a class and update all imports in one atomic call:

```json
batch_edit(path="/project", operations=[
    {"op": "replace", "file": "src/core.py",       "edits": [{"line": 5,  "old": "class OldName:", "new": "class NewName:"}]},
    {"op": "replace", "file": "src/api.py",         "edits": [{"line": 2,  "old": "from core import OldName", "new": "from core import NewName"}]},
    {"op": "replace", "file": "tests/test_core.py", "edits": [
        {"line": 1, "old": "from core import OldName", "new": "from core import NewName"},
        {"line": 10, "old": "OldName()", "new": "NewName()"}
    ]}
])
```

**1 tool call** instead of 3+ sequential edits.

## Create and populate a new module

Create a file and add its import in one atomic batch:

```json
batch_edit(path="/project", operations=[
    {"op": "create", "file": "src/utils.py", "content": "\"\"\"Shared utilities.\"\"\"\n\ndef helper():\n    return 42\n"},
    {"op": "replace", "file": "src/main.py", "edits": [
        {"line": 3, "old": "# imports", "new": "from utils import helper  # imports"}
    ]}
])
```

## Roll back after a failed edit

Every `batch_edit` call returns a `checkpoint` snapshot payload — a JSON
string, **not** a short SHA. Pass that exact payload straight back to
`batch_rollback` to restore the previous state:

```python
from axm_edit.tools.batch_edit import BatchEditTool
from axm_edit.tools.batch_rollback import BatchRollbackTool

result = BatchEditTool().execute(path="/my/project", operations=[...])
checkpoint = result.data["checkpoint"]  # the full snapshot payload

rollback = BatchRollbackTool()
rollback.execute(path="/my/project", checkpoint=checkpoint)
# All touched files restored to their pre-edit state
```

!!! warning "The checkpoint is the whole snapshot, not a hash"
    `checkpoint` carries the pre-edit bytes of every touched path as a JSON
    string. Store it verbatim and hand it back unchanged; a placeholder like
    `"abc123def"` is rejected (`RollbackResult(valid=False)` → "Rollback
    failed").

## Search then edit

`batch_edit` matches each `old` against **whole file lines**, never as a
substring: an `old` of `"deprecated_func"` will *not* match the line
`x = deprecated_func()`. So build every edit from the **full matched line**
`search_files` returns, and compute `new` by replacing within it:

```python
from axm_edit.tools.search_files import SearchFilesTool
from axm_edit.tools.batch_edit import BatchEditTool

# Step 1: find all occurrences
search = SearchFilesTool()
hits = search.execute(path="/project", pattern="deprecated_func", include=["*.py"])

# Step 2: build operations from search results — old is the WHOLE line.
ops = []
for match in hits.data["matches"]:
    old_line = match["content"]  # the full source line the match sits on
    ops.append({
        "op": "replace",
        "file": match["file"],
        "edits": [{
            "line": match["line"],
            "old": old_line,
            "new": old_line.replace("deprecated_func", "new_func"),
        }],
    })

# Step 3: apply all at once
edit = BatchEditTool()
edit.execute(path="/project", operations=ops)
```

For a genuine **substring** replace in one file, reach for `edit_file`
(`old`/`new` are matched as substrings) instead of `batch_edit`.
