# Reference

## MCP Tools

| Tool | Entry point | Description |
|---|---|---|
| `git_preflight` | `GitPreflightTool` | Working tree status and diff summary |
| `git_branch` | `GitBranchTool` | Create or checkout branches |
| `git_commit` | `GitCommitTool` | Batched atomic commits with pre-commit |
| `git_tag` | `GitTagTool` | One-shot semver tagging |

## Lifecycle Hooks

Hook actions auto-discovered via the `axm.hooks` entry-point group by `HookRegistry.with_builtins()` in `axm-engine`.

| Hook | Entry point | Description |
|---|---|---|
| `git:create-branch` | `CreateBranchHook` | Create session branch `{prefix}/{session_id}` |
| `git:commit-phase` | `CommitPhaseHook` | Stage all + commit with `[axm] {phase}` |
| `git:merge-squash` | `MergeSquashHook` | Squash-merge session branch back to target |

## Python API

Auto-generated API reference is available under [Python API](api/).
