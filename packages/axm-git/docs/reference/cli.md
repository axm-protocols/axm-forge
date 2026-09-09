# Tool reference

All tools return `ToolResult`; `success`, `error`, `data` and `text` are
envelope fields. Tables describe success payloads unless stated otherwise.
Early failures may omit data. Unknown keyword arguments are not safety checks:
implementations can ignore them.

## Arguments

All arguments are keyword-only in Python. Every tool has `path="."`.
Use the repository root unless the described operation requires a package
directory (release tools), a scope (preflight), or a parent directory (clone).
The CLI spelling uses hyphens, for example `--diff-lines`.

| Tool | Other arguments (exact defaults) | Success data |
|---|---|---|
| `git_preflight` | `diff_lines=200` (0 disables patch) | `files`, `file_count`, `diff_stat`, `diff`, `diff_truncated`, `clean` |
| `git_branch` | required `name`; `from_ref=None`, `checkout_only=False`, `delete=False` | `branch`; deletion adds `deleted=True` |
| `git_commit` | `commits=None` (empty rejected), `profile=None`, `strict=False` | `results`, `total`, `succeeded`, `hook_autofixed_files`, `author` |
| `git_clone` | required `url`, `dest` | `url`, `dest`, absolute `path`, `cloned` |
| `git_worktree` | required `action` (`add`/`remove`/`list`); `worktree_path=None`, `branch=None`, `base=None`, `force=False` | list: `worktrees`; add: `path`, `branch`, `base`; remove: `removed` |
| `git_merge` | required `branch`; `target_branch=None`, `message=None` | `merged` (source branch), `into`, `message` |
| `git_pull` | `branch="main"`, `remote="origin"` | `pulled`, `remote`, `branch` |
| `git_push` | `remote="origin"`, `set_upstream=True`, `force=False`, `force_unconditional=False` | `branch`, `remote`, `pushed`, `set_upstream`, `force_mode` |
| `git_pr` | required `title`; `body=None`, `base=None`, `auto_merge=False` | `pr_url`, `pr_number`, `auto_merge`; recovery adds `already_existed=True` |
| `git_await_merge` | required `pr` (string number or URL); `timeout=600`, `interval=30` (seconds) | `merged=True`, `pr_ref` |
| `git_release_diff` | none | `current_tag`, `suggested_bump`, `suggested_next`, `breaking`, `commits_since`, `counts`, `files_changed`, `diffstat`, `public_api_touched` |
| `git_tag` | `version=None` | `tag`, `full_tag`, `bump`, `breaking`, `resolved_version`, `pushed`, `ci_check`, `commits_included`, `current_tag` |

A `None` branch base/target resolves the repository default for worktree,
merge and PR. Pull instead defaults literally to `main`.
The default squash message is `Merge <branch> (squash)`.

## Effects and recovery

- [Commits](../howto/commits.md): spec shape, partial failures, index refusal,
  retry marker, observed autofix paths and author result.
- [Branches/worktrees/PRs](../howto/collaboration.md): forced deletion/removal,
  squash-only merge, checkout changes, pull, push and auto-merge.
- [Release tools](../howto/releases.md): package prefix, CI guard, analysis
  scope, tag push and local-tag retention on failure.

`git_tag` is always create-and-push; `git_merge` is local squash-only.
Neither tool has an `action`, `dry_run` or `strategy` option.
Only `git_worktree` has the listed `action` argument.

## Python import and entry-point mapping

The following classes are registered under `axm.tools`. Import from their
modules, not from the package root.

| Tool | Module | Class |
|---|---|---|
| `git_preflight` | `axm_git.tools.commit_preflight` | `GitPreflightTool` |
| `git_branch` | `axm_git.tools.branch` | `GitBranchTool` |
| `git_commit` | `axm_git.tools.commit` | `GitCommitTool` |
| `git_clone` | `axm_git.tools.clone` | `GitCloneTool` |
| `git_worktree` | `axm_git.tools.worktree` | `GitWorktreeTool` |
| `git_merge` | `axm_git.tools.merge` | `GitMergeTool` |
| `git_pull` | `axm_git.tools.pull` | `GitPullTool` |
| `git_push` | `axm_git.tools.push` | `GitPushTool` |
| `git_pr` | `axm_git.tools.pr` | `GitPRTool` |
| `git_await_merge` | `axm_git.tools.await_merge` | `GitAwaitMergeTool` |
| `git_release_diff` | `axm_git.tools.release_diff` | `GitReleaseDiffTool` |
| `git_tag` | `axm_git.tools.tag` | `GitTagTool` |

```python
from axm_git.tools.commit_preflight import GitPreflightTool

result = GitPreflightTool().execute(path=".", diff_lines=0)
if result.success:
    print(result.data["clean"])
else:
    print(result.error)
```

See [CLI and MCP](../howto/mcp.md) for dispatch and
[generated API](axm_git/index.md) for source-derived module details.
Generated coverage includes internals; root exports are only version metadata.
