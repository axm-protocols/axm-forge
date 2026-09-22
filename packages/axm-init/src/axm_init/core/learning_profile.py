"""Thin routing to Learning-owned metadata; no bundled domain implementation."""

from pathlib import Path
from typing import cast

from axm_init.scaffolding import provider_hook

__all__ = [
    "declared_learning_domain",
    "merge_learning_metadata",
    "register_learning_profile",
]


def merge_learning_metadata(metadata: str, domain: str, module_name: str) -> str:
    """Delegate metadata merging to the required Learning provider."""
    return cast(
        str,
        provider_hook("learning", "merge_learning_metadata")(
            metadata, domain, module_name
        ),
    )


def declared_learning_domain(
    root: Path, requested_domain: str | None = None
) -> str | None:
    """Delegate profile discovery to the required Learning provider."""
    return cast(
        str | None,
        provider_hook("learning", "declared_learning_domain")(root, requested_domain),
    )


def register_learning_profile(root: Path, domain: str, module_name: str) -> None:
    """Delegate profile registration to the required Learning provider."""
    provider_hook("learning", "register_learning_profile")(root, domain, module_name)
