# Reference

## MCP Tools

| Tool | Entry point | Description |
|---|---|---|
| `git_preflight` | `GitPreflightTool` | Working tree status and diff summary |
| `git_branch` | `GitBranchTool` | Create or checkout branches |
| `git_commit` | `GitCommitTool` | Batched atomic commits with commit-hook handling; warns on non-Conventional-Commit messages (`strict=True` blocks them) |
| `git_clone` | `GitCloneTool` | Clone a repository into a local directory |
| `git_tag` | `GitTagTool` | One-shot semver tagging |
| `git_release_diff` | `GitReleaseDiffTool` | Read-only SemVer bump decision: scopes commits/diffstat to a package subdir since its last tag, flags public-API changes, and suggests the next version |
| `git_push` | `GitPushTool` | Push with dirty-check and auto-upstream; `force` uses `--force-with-lease` by default, `force_unconditional` for a bare `--force` |
| `git_worktree` | `GitWorktreeTool` | Add, remove, or list git worktrees; `path` is the repo and `worktree_path` the (possibly not-yet-existing) worktree location |
| `git_merge` | `GitMergeTool` | Squash-merge a branch into its target; refuses a dirty tree and rolls back on conflict |
| `git_pull` | `GitPullTool` | Pull `origin main` (override via `remote`/`branch`) into the local repo |
| `git_await_merge` | `GitAwaitMergeTool` | Poll a PR (`pr`: number or URL) until merged or timeout |
| `git_pr` | `GitPRTool` | Create GitHub pull requests with optional auto-merge; idempotent — recovers the existing PR (`already_existed`) when one is already open |


## Python API

Auto-generated API reference is available under [Python API](../reference/axm_git/index.md).
