# Serialise integration with the repository lock

Anything that moves or undoes a lane of a repository (replaying an attempt's
commits and fast-forwarding the lane, or rolling an attempt back and removing
its worktree) must run under the repository's integration lock. The warden and
the tribunal dev graphs (`dev.work.exec`, the land graph) take this one lock,
so they never interleave on the same repository.

```python
from axm_git.core.lock import RepositoryLockTimeoutError, repository_lock

try:
    with repository_lock(worktree_path, timeout=300.0) as lock_file:
        ...  # replay, fast-forward or roll back
except RepositoryLockTimeoutError:
    ...  # another integrator kept the lock past the timeout
```

| Symbol | Contract |
|---|---|
| `repository_lock(repo_path, *, timeout)` | Context manager; waits at most `timeout` seconds (`0` tries once), yields the lock file's `Path` |
| `repository_lock_path(repo_path)` | The lock file of the repository holding `repo_path`, `None` outside git |
| `RepositoryLockTimeoutError` | Subclass of `TimeoutError`, raised when the wait runs out |
| `INTEGRATION_LOCK_NAME` | `"axm-integration.lock"` |

`repository_lock` raises `ValueError` when `repo_path` is not inside a git
repository. The symbols are also re-exported from `axm_git.core`.

## The protocol

The lock is an advisory exclusive `flock(2)` on `axm-integration.lock` inside
the repository's **common** git directory
(`git rev-parse --path-format=absolute --git-common-dir`):

- every worktree of one repository resolves to the same file, so they contend;
- distinct repositories never contend;
- the kernel releases the lock when its holder exits, so a crashed holder
  leaves no stale lock behind (the file itself stays, harmlessly);
- it is not re-entrant: taking it again from the same process while held
  times out, so hold it once around the whole critical section.

Any process, in any language, that takes an exclusive `flock` on that file
excludes and is excluded by `repository_lock`. The file name is part of the
protocol: renaming it requires migrating every holder at once.
