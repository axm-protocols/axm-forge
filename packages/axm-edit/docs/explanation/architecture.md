# Architecture

Design decisions and module layout for `axm-edit`.

## Design: 1 Tool, 1 JSON

The core design choice is a **single `batch_edit` tool** that handles replace, create, and delete operations in one atomic call. A refactor that modifies, creates, and deletes files in the same operation requires just 1 tool call instead of N.

## Module layout

```
src/axm_edit/
├── __init__.py              # Package root
├── models/
│   └── operations.py        # Pydantic models (Edit, ReplaceOp, CreateOp, DeleteOp, BatchResult)
├── core/
│   ├── engine.py            # Validate-then-apply batch engine
│   └── checkpoint.py        # Git stash checkpoint / rollback
├── tools/
│   ├── batch_edit.py         # BatchEditTool (AXMTool protocol)
│   ├── batch_rollback.py     # BatchRollbackTool (AXMTool protocol)
│   ├── read_file.py          # ReadFileTool (AXMTool protocol)
│   ├── search_files.py       # SearchFilesTool (AXMTool protocol)
│   ├── list_dir.py           # ListDirTool (AXMTool protocol)
│   ├── run_command.py        # RunCommandTool (AXMTool protocol)
│   └── write_file.py         # WriteFileTool (AXMTool protocol)
└── utils/
    └── __init__.py           # Shared utilities (is_binary)
```

## The line-shift problem

When an edit at line 10 replaces 2 lines with 3 lines, every line number after 10 shifts by +1. If a second edit targets line 15 of the **original** file, applying it after the first edit would hit the wrong line.

**Solution:** All line numbers in edits reference the **original file** (the snapshot the agent read). The engine:

1. Reads the file once (snapshot)
2. Validates **all** `old` anchors against the snapshot
3. Sorts edits **bottom-to-top** (descending line number)
4. Applies in that order — upper lines are never shifted by lower edits
5. Writes the result

## Atomicity

- **Checkpoint**: `git stash create` before applying (returns SHA for rollback)
- **Validation first**: All checks pass before any file is touched
- **Rollback**: `batch_rollback` restores via `git checkout + clean + stash apply`

## Security

| Constraint | Reason |
|---|---|
| Relative paths only | No access outside the project |
| `../` blocked | No path traversal |
| `old` required for replace | No blind modifications |
| Validation before write | Fail-fast, 0 files corrupted |
| Git checkpoint | Rollback always possible |
| `agent_hint` on tools | LLM-optimized description propagates to MCP — agents see what each tool does without parsing docstrings |
