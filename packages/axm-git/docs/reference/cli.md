# Reference

## MCP Tools

| Tool | Entry point | Description |
|---|---|---|
| `git_preflight` | `GitPreflightTool` | Working tree status and diff summary |
| `git_branch` | `GitBranchTool` | Create or checkout branches |
| `git_commit` | `GitCommitTool` | Batched atomic commits with pre-commit; warns on non-Conventional-Commit messages (`strict=True` blocks them) |
| `git_clone` | `GitCloneTool` | Clone a repository into a local directory |
| `git_tag` | `GitTagTool` | One-shot semver tagging |
| `git_push` | `GitPushTool` | Push with dirty-check and auto-upstream; `force` uses `--force-with-lease` by default, `force_unconditional` for a bare `--force` |
| `git_worktree` | `GitWorktreeTool` | Add, remove, or list git worktrees |
| `git_pr` | `GitPRTool` | Create GitHub pull requests with optional auto-merge; idempotent — recovers the existing PR (`already_existed`) when one is already open |

## Lifecycle Hooks

Hook actions auto-discovered via the `axm.hooks` entry-point group by `HookRegistry.with_builtins()` in `axm-engine`.

| Hook | Entry point | Description |
|---|---|---|
| `git:preflight` | `PreflightHook` | Structured working tree status check before a phase |
| `git:create-branch` | `CreateBranchHook` | Create session branch; accepts `branch`, `ticket_id`, `ticket_title`, `ticket_labels` to override or derive branch name |
| `git:branch-delete` | `BranchDeleteHook` | Delete a branch via `git branch -D`; reads name from `branch` param then `branch` context key |
| `git:commit-phase` | `CommitPhaseHook` | Stage all + commit with `[axm] {phase}`; pass `from_outputs=True` to derive staged files from protocol outputs |
| `git:merge-squash` | `MergeSquashHook` | Squash-merge branch back to target; accepts `branch` and `message` params, reads branch from context when not supplied |
| `git:worktree-add` | `WorktreeAddHook` | Create a worktree + branch for a ticket at `<repo_parent>/<ticket_id>/` |
| `git:worktree-remove` | `WorktreeRemoveHook` | Remove a worktree previously created by `WorktreeAddHook` |
| `git:push` | `PushHook` | Push the current branch to `origin -u`; reads `branch` from context or detects HEAD |
| `git:pull-main` | `PullHook` | Pull `origin main` (override via `remote`/`branch` params) into the local repository |
| `git:create-pr` | `CreatePRHook` | Run `gh pr create` then `gh pr merge --auto --squash`; skips when `gh` is unavailable |
| `git:await-merge` | `AwaitMergeHook` | Poll a PR (`pr_number`/`pr_url`) until merged or timeout |

## Python API

Auto-generated API reference is available under [Python API](../reference/axm_git/index.md).
