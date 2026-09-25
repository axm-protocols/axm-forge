"""Explicit Learning check routed to its required installed provider."""

from pathlib import Path
from typing import cast

from axm_init.models.check import CheckResult

__axm_explicit_only__ = True


def check_learning_profile(project: Path) -> CheckResult:
    """Execute Learning-owned validation without a bundled fallback."""
    from axm_init.scaffolding import provider_hook

    return cast(
        CheckResult, provider_hook("learning", "check_learning_profile")(project)
    )
