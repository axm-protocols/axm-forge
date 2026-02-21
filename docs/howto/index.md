# How-To Guides

Task-oriented guides for common workflows.

## Commit deleted files

When a file has been removed from disk, `git_commit` handles it automatically via `git add -A --`:

```python
from axm_git.tools.commit import GitCommitTool

# File was already deleted from disk
result = GitCommitTool().execute(
    path="/path/to/repo",
    commits=[{"files": ["old_module.py"], "message": "fix: remove dead module"}],
)
# success=True — deletion is committed
```

## Handle pre-commit auto-fixes

When ruff or another tool auto-fixes files during `git commit`, the tool retries automatically:

```python
result = GitCommitTool().execute(
    path="/path/to/repo",
    commits=[{"files": ["src/foo.py"], "message": "feat: add foo"}],
)
# If ruff auto-fixed, result.data["results"][0]["retried"] == True
```

If the retry also fails (e.g. mypy error), the result includes:

```python
result.data["failed_commit"]["auto_fixed_files"]  # ["src/foo.py"]
result.data["failed_commit"]["retried"]  # True
result.data["failed_commit"]["precommit_output"]  # full hook output
```

## Tag without GitHub CLI

The `git_tag` tool works without `gh` installed — CI checks are simply skipped:

```python
result = GitTagTool().execute(path="/path/to/repo")
# result.data["ci_check"] == "skipped" if gh not available
```

## Handle non-git directory errors

When a tool is called on a directory that isn't a git repository but contains git subdirectories (e.g. a monorepo parent), the error includes suggestions:

```python
result = GitPreflightTool().execute(path="/path/to/monorepo")
# result.success == False
# result.error == "fatal: not a git repository. This directory contains
#   git repos: axm-ast, axm-core, axm-git. Pass one of these as the path instead."
# result.data["suggestions"] == ["axm-ast", "axm-core", "axm-git"]
```

This works for all three tools (`git_preflight`, `git_commit`, `git_tag`).

## Use with MCP

All tools are auto-discovered via `axm.tools` entry points. Through the AXM MCP server, call them as:

```
git_preflight(path="/path/to/repo")
git_commit(path="/path/to/repo", commits=[...])
git_tag(path="/path/to/repo")
```
