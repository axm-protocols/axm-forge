# Inspect a repository

Learn the result model without changing repository or remote state.

## Install

Use Python 3.12+ and a Git repository that already contains commits.

```bash
uv add axm-git
axm git_preflight --help
axm git_preflight --path . --diff-lines 0
```

Run from the repository root. Replace `.` with an absolute repository path
when your current directory is elsewhere. Installation changes your Python
project environment; the preflight operation only reads Git state.

## Inspect through Python

This complete snippet inspects the current directory:

```python
from axm_git.tools.commit_preflight import GitPreflightTool

result = GitPreflightTool().execute(path=".", diff_lines=0)
if not result.success:
    raise RuntimeError(result.error)
print(result.data["clean"])
print(result.data["files"])
print(result.text)
```

`files` contains status/path records; `clean` means there are no status entries
in the inspected scope. Setting `diff_lines=0` suppresses patch content.
The `text` field belongs to the result envelope, not inside `data`.

Passing a package directory scopes this inspection to that directory.
It does not prove that sibling packages or the repository root are clean.
The diff summary comes from Git's unstaged diff; it is not a complete
inventory of every staged or untracked file's contents.

## Inspect release history

From the package root, use:

```bash
axm git_release_diff --path .
```

The result suggests a version and summarizes package-scoped history. It does
not create a tag, fetch remote tags or publish anything. Read the
[release limitations](../howto/releases.md) before treating the suggestion as
a publication decision.

Continue with [committing explicit files](../howto/commits.md) or
[CLI and MCP dispatch](../howto/mcp.md). Those guides identify mutations
before showing their calls.
