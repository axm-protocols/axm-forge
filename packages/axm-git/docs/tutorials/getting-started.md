# Getting Started

This tutorial walks you through installing `axm-git` and using the MCP tools.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Git initialized repository

## Installation

```bash
uv add axm-git
```

Or with pip:

```bash
pip install axm-git
```

## Step 1: Check Working Tree Status

Use `git_preflight` to see what files have changed:

```python
from axm_git.tools.commit_preflight import GitPreflightTool

result = GitPreflightTool().execute(path="/path/to/repo")
print(result.data)
# {
#   "files": [{"path": "src/foo.py", "status": "M"}, ...],
#   "diff_stat": "src/foo.py | 3 ++-\n ...",
#   "clean": False,
#   "file_count": 2
# }
```

## Step 2: Create a Branch

Use `git_branch` to create or switch to a feature branch:

```python
from axm_git.tools.branch import GitBranchTool

result = GitBranchTool().execute(name="feat/new-feature", path="/path/to/repo")
print(result.data)
# {"branch": "feat/new-feature"}
```

!!! tip "Checkout existing branch"
    Pass `checkout_only=True` to switch to an existing branch without creating a new one.

## Step 3: Commit Changes

Use `git_commit` to stage and commit files in batches:

```python
from axm_git.tools.commit import GitCommitTool

result = GitCommitTool().execute(
    path="/path/to/repo",
    commits=[
        {"files": ["src/foo.py"], "message": "feat: add foo module"},
        {"files": ["tests/test_foo.py"], "message": "test: add foo tests"},
    ],
)
print(result.data["results"])
# [{"sha": "abc1234", "message": "feat: add foo module", "precommit_passed": True}, ...]
```

!!! tip "Auto-retry"
    If a pre-commit hook (like ruff) auto-fixes a file, `git_commit` automatically
    re-stages and retries the commit once.

## Step 4: Create a Release Tag

Use `git_tag` to compute the next semver version and push the tag:

```python
from axm_git.tools.tag import GitTagTool

result = GitTagTool().execute(path="/path/to/repo")
print(result.data)
# {"tag": "v0.2.0", "previous": "v0.1.0", "bump": "minor",
#  "reason": "feat: add foo module", "pushed": True}
```

The tool automatically:

1. Checks the tree is clean
2. Checks CI status via `gh` (if available)
3. Analyzes commits since the last tag
4. Computes the semver bump based on Conventional Commits
5. Creates and pushes the annotated tag

## Step 5: Push to Remote

Use `git_push` to push the current branch with safety checks:

```python
from axm_git.tools.push import GitPushTool

result = GitPushTool().execute(path="/path/to/repo")
print(result.data)
# {"branch": "feat/new-feature", "remote": "origin",
#  "pushed": True, "set_upstream": True}
```

The tool verifies the tree is clean before pushing, and automatically sets the upstream for new branches.

## Next Steps

- [Architecture](../explanation/architecture.md) — How the project is structured
- [API Reference](../reference/api/) — Full API documentation
