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

Every `batch_edit` call returns a `checkpoint` SHA. Use it to restore the previous state:

```python
from axm_edit.tools.batch_rollback import BatchRollbackTool

tool = BatchRollbackTool()
result = tool.execute(path="/my/project", checkpoint="abc123def")
# All files restored to pre-edit state
```

## Search then edit

Combine `search_files` and `batch_edit` for a find-and-replace workflow:

```python
from axm_edit.tools.search_files import SearchFilesTool
from axm_edit.tools.batch_edit import BatchEditTool

# Step 1: find all occurrences
search = SearchFilesTool()
hits = search.execute(path="/project", pattern="deprecated_func", include=["*.py"])

# Step 2: build operations from search results
ops = []
for match in hits.data["matches"]:
    ops.append({
        "op": "replace",
        "file": match["file"],
        "edits": [{"line": match["line"], "old": "deprecated_func", "new": "new_func"}],
    })

# Step 3: apply all at once
edit = BatchEditTool()
edit.execute(path="/project", operations=ops)
```
