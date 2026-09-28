"""Core logic — subprocess runners, semver computation, repository lock."""

from axm_git.core.commit_cmd import build_commit_cmd
from axm_git.core.commit_spec import (
    attempt_commit_with_autofix_retry,
    validate_commit_spec,
)
from axm_git.core.identity import (
    GitIdentity,
    GitProfileConfig,
    author_args,
    load_config,
    resolve_identity,
)
from axm_git.core.lock import (
    INTEGRATION_LOCK_NAME,
    RepositoryLockTimeoutError,
    repository_lock,
    repository_lock_path,
)

__all__ = [
    "INTEGRATION_LOCK_NAME",
    "GitIdentity",
    "GitProfileConfig",
    "RepositoryLockTimeoutError",
    "attempt_commit_with_autofix_retry",
    "author_args",
    "build_commit_cmd",
    "load_config",
    "repository_lock",
    "repository_lock_path",
    "resolve_identity",
    "validate_commit_spec",
]
