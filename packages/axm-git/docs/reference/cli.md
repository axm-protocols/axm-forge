# Reference

## MCP Tools

| Tool | Entry point | Description |
|---|---|---|
| `git_preflight` | `GitPreflightTool` | Working tree status and diff summary |
| `git_branch` | `GitBranchTool` | Create or checkout branches |
| `git_commit` | `GitCommitTool` | Batched atomic commits with pre-commit |
| `git_tag` | `GitTagTool` | One-shot semver tagging |
| `git_push` | `GitPushTool` | Push with dirty-check and auto-upstream |
| `git_worktree` | `GitWorktreeTool` | Add, remove, or list git worktrees |
| `git_pr` | `GitPRTool` | Create GitHub pull requests with optional auto-merge |

## Lifecycle Hooks

Hook actions auto-discovered via the `axm.hooks` entry-point group by `HookRegistry.with_builtins()` in `axm-engine`.

| Hook | Entry point | Description |
|---|---|---|
| `git:preflight` | `PreflightHook` | Structured working tree status check before a phase |
| `git:create-branch` | `CreateBranchHook` | Create session branch; accepts `branch`, `ticket_id`, `ticket_title`, `ticket_labels` to override or derive branch name |
| `git:commit-phase` | `CommitPhaseHook` | Stage all + commit with `[axm] {phase}`; pass `from_outputs=True` to derive staged files from protocol outputs |
| `git:merge-squash` | `MergeSquashHook` | Squash-merge branch back to target; accepts `branch` and `message` params, reads branch from context when not supplied |
| `git:worktree-add` | `WorktreeAddHook` | Create a worktree + branch for a ticket at `<repo_parent>/<ticket_id>/` |
| `git:worktree-remove` | `WorktreeRemoveHook` | Remove a worktree previously created by `WorktreeAddHook` |

## Python API

Auto-generated API reference is available under [Python API](api/).
