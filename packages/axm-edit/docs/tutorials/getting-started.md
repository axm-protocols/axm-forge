# Getting Started

This tutorial walks you through installing `axm-edit` and using its core tools in 5 minutes.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
uv add axm-edit
```

Or with pip:

```bash
pip install axm-edit
```

## Step 1: Read a file

```python
from axm_edit.tools.read_file import ReadFileTool

tool = ReadFileTool()
result = tool.execute(path="/my/project", file="src/main.py")
print(result.data["content"])
# Output: line-numbered file content
```

## Step 2: Search across files

```python
from axm_edit.tools.search_files import SearchFilesTool

tool = SearchFilesTool()
result = tool.execute(
    path="/my/project",
    pattern="TODO",
    include=["*.py"],
)
for match in result.data["matches"]:
    print(f"{match['file']}:{match['line']}: {match['content']}")
```

## Step 3: Batch edit

Replace, create, and delete files in a single atomic call:

```python
from axm_edit.tools.batch_edit import BatchEditTool

tool = BatchEditTool()
result = tool.execute(
    path="/my/project",
    operations=[{
        "op": "replace",
        "file": "src/main.py",
        "edits": [{"old": "old_name", "new": "new_name"}],
    }],
)
print(result.data["summary"])
# {"modified": 1, "created": 0, "deleted": 0}
```

## Step 4: Run a command

```python
from axm_edit.tools.run_command import RunCommandTool

tool = RunCommandTool()
result = tool.execute(
    path="/my/project",
    command="python -m pytest -x -q",
    timeout=60,
)
print(result.data["stdout"])
```

## Step 5: Rollback if needed

Every `batch_edit` returns a `checkpoint` SHA you can use to restore state:

```python
from axm_edit.tools.batch_rollback import BatchRollbackTool

tool = BatchRollbackTool()
result = tool.execute(path="/my/project", checkpoint="<sha-from-batch-edit>")
```

## Next steps

- [How-To Guides](../howto/index.md) — Task-oriented recipes
- [API Reference](../reference/) — Full module documentation
- [Architecture](../explanation/architecture.md) — Design decisions and module layout
