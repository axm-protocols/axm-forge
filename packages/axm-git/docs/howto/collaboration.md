# Branches, worktrees and collaboration

These are separate operations with different local and remote effects.
All argument examples below are logical tool calls; dispatch them as described
in [CLI and MCP](mcp.md).

## Work locally

`git_branch(name="feat/example", path="/repo")` creates and checks out a new
branch. Use `checkout_only=True` to switch to an existing branch; creating a
branch that already exists does not automatically switch to it.
`from_ref` sets the creation base. `delete=True` force-deletes the local
branch with `git branch -D`, including an unmerged branch.

For an isolated checkout, use an existing repository as `path` and a distinct
future directory as `worktree_path`:

```json
{
  "name": "git_worktree",
  "arguments": {
    "action": "add",
    "path": "/absolute/repository",
    "worktree_path": "/absolute/repository-example",
    "branch": "feat/example",
    "base": "main"
  }
}
```

`branch` requests a **new** branch (`-b`). Listing uses `action="list"`;
removal uses `action="remove"` and the same two paths. `force=True` permits
forced removal and can discard work. Removal does not also delete the branch.

## Merge locally

`git_merge(branch="feat/example", target_branch="main", path="/repo")`
requires a clean working tree, checks out the target, performs
`merge --squash`, and commits the result. It does not push, delete the source
branch or merge a GitHub PR. There is no alternate merge-strategy option.

If the squash step fails, it runs `reset --hard` on the target to clear the
conflicted state. It does not restore the previously checked-out branch.
A later commit-hook failure is a different path: staged squash changes can
remain and there is no commit-tool autofix retry. Inspect state before recovery.

## Obtain and publish changes

`git_clone(url=..., dest=..., path=...)` creates the destination relative to
its parent `path`. It accepts a remote URL or local repository source. Clone
has no built-in subprocess timeout; callers needing a hard deadline must
provide one externally.

`git_pull(branch="main", remote="origin", path="/repo")` pulls into the
**current** branch; it does not check out main. Pull follows Git configuration
and has no extra clean-tree guard or rollback. Inspect any conflict state.

`git_push(path="/repo")` requires a clean tree and a checked-out branch.
It pushes to `origin`, setting upstream when absent by default.
`force=True` uses `--force-with-lease`; its protection depends on local
remote-tracking state. `force=True, force_unconditional=True` uses bare
`--force` and can discard remote commits.

## GitHub PRs

After publishing the branch, `git_pr(title=..., body=..., base=..., path=...)`
creates a remote PR through authenticated gh. A recognized “already exists”
error recovers the open PR and returns `already_existed=True`; it does not
update that PR's title/body or apply the requested auto-merge.

For a newly created PR, `auto_merge=True` attempts squash auto-merge.
Check the returned `auto_merge`: PR creation can succeed even if enabling
auto-merge fails. The default is false.

`git_await_merge(pr="123", path="/repo", timeout=600, interval=30)` polls until
merged, closed without merging, query failure or timeout. It does not trigger
a merge. The interval and subprocess duration mean this is not a precise
wall-clock deadline. It returns `merged=True` and `pr_ref` on success.
