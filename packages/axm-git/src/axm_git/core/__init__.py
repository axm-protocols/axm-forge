"""Core logic — subprocess runners and semver computation."""

from axm_git.core.commit_spec import (
    attempt_commit_with_autofix_retry,
    build_commit_result,
    retry_commit_on_autofix,
    validate_commit_spec,
)
from axm_git.core.identity import (
    GitIdentity,
    GitProfileConfig,
    author_args,
    load_config,
    resolve_identity,
)

__all__ = [
    "GitIdentity",
    "GitProfileConfig",
    "attempt_commit_with_autofix_retry",
    "author_args",
    "build_commit_result",
    "load_config",
    "resolve_identity",
    "retry_commit_on_autofix",
    "validate_commit_spec",
]
