# Use via MCP

`axm-git` exposes its CLI commands as MCP (Model Context Protocol) tools via `axm-mcp`. AI agents can call them directly without spawning subprocesses.

!!! info "Setup"
    These tools are served by `axm-mcp`. If you haven't connected the server yet,
    see the **[axm-mcp Quick Start](https://forge.axm-protocols.io/mcp/tutorials/quickstart/)** —
    one command connects the whole toolchain. No per-package install needed.

## Available Tools

| MCP Tool | Purpose |
|---|---|
| `git_preflight` | Working tree status and diff summary before a phase |
| `git_branch` | Create or checkout a branch |
| `git_commit` | Batched atomic commits with pre-commit; warns on non-Conventional-Commit messages (`strict=True` blocks them), retries on pre-commit auto-fixes |
| `git_clone` | Clone a repository into a local directory |
| `git_tag` | One-shot semver tagging (skips CI checks when `gh` is unavailable) |
| `git_push` | Push with dirty-check and auto-upstream; `force` uses `--force-with-lease` by default |
| `git_pull` | Pull `origin main` (override via `remote` / `branch`) into the local repo |
| `git_worktree` | Add, remove, or list git worktrees |
| `git_pr` | Create GitHub pull requests with optional auto-merge; idempotent — recovers an existing open PR |
| `git_merge` | Squash-merge a branch back into its target; refuses to run on a dirty working tree, and rolls back via `git reset --hard` if the squash conflicts so the repo is left clean |
| `git_await_merge` | Poll a PR (`pr_number` / `pr_url`) until merged or timeout |

## Usage

!!! note "MCP dispatch"
    The examples below show the **logical API** — the parameters each tool takes.
    In practice, AI agents call these via MCP tool dispatch (e.g. `mcp_axm-mcp_git_commit`),
    not direct Python imports.

```
git_preflight(path="/path/to/repo")
git_branch(name="feat/new-thing", path="/path/to/repo")
git_commit(path="/path/to/repo", commits=[{"files": ["src/foo.py"], "message": "feat: add foo"}])
```

`git_commit` handles staging internally (including deletions via `git add -A`), so you never run `git add` separately.

## Entry Points

All tools are auto-discovered via the `axm.tools` entry-point group — see the
[CLI Reference](../reference/cli.md) for the full tool / class mapping.
`axm-mcp` discovers these automatically at startup.
