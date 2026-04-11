"""Core logic — subprocess runners and semver computation."""

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
    "author_args",
    "load_config",
    "resolve_identity",
]
