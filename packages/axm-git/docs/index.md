# axm-git

Structured Git operations for the AXM CLI, MCP and Python callers.
The package wraps the Git and GitHub CLIs and returns a `ToolResult` with
`success`, `data`, `error` and a separate compact `text` rendering.

Start with [inspect a repository](tutorials/getting-started.md).
It does not create commits, branches, tags or remote objects.

| Your objective | Read |
|---|---|
| Call tools from CLI or an agent | [CLI and MCP](howto/mcp.md) |
| Commit explicit files and recover from refusal | [Commits and hooks](howto/commits.md) |
| Create a branch, worktree or PR | [Branches and collaboration](howto/collaboration.md) |
| Inspect a version bump or publish a tag | [Releases](howto/releases.md) |
| Select a commit author | [Author identity](howto/identity.md) |
| Check exact arguments and result keys | [Tool reference](reference/cli.md) |
| Understand boundaries and guarantees | [Architecture](explanation/architecture.md) |

## Effects at a glance

`git_preflight`, `git_release_diff` and worktree listing inspect local state.
`git_branch`, `git_commit`, `git_merge` and worktree add/remove mutate local state.
`git_clone` and `git_pull` obtain remote content and write locally.
`git_push`, `git_pr` and `git_tag` affect remote state.
`git_await_merge` only observes GitHub.

**Tagging includes a push to origin.** There is no tag preview/list action.
The [release guide](howto/releases.md) distinguishes the read-only analysis
from publication and explains the CI guard's limits.

## Interfaces

Install with `uv add axm-git` in a Python 3.12+ environment containing Git.
Tools are registered in `axm.tools`; GitHub authentication is declared through
`axm.credentials`. Git commit hooks continue to run normally.

The [generated Python API](reference/axm_git/index.md) includes tool classes
and internal helpers. Only version metadata is exported from `axm_git` itself.
