"""Branch naming convention for ticket-driven workflows."""

from __future__ import annotations

import re

__all__ = ["branch_name_from_ticket", "slugify"]

LABEL_TO_TYPE: dict[str, str] = {
    "feature": "feat",
    "enhancement": "feat",
    "bug": "fix",
    "refactor": "refactor",
    "documentation": "docs",
    "test": "test",
}


def slugify(title: str, *, max_len: int = 40) -> str:
    """Convert a title string into a URL-safe slug.

    Lowercases the input, replaces non-alphanumeric characters with hyphens,
    collapses consecutive hyphens, and strips leading/trailing hyphens.

    Args:
        title: The title to slugify.
        max_len: Maximum length of the slug (default 40). Truncation
            prefers word boundaries when possible.

    Returns:
        A sanitized slug, or ``"untitled"`` if the title is empty or
        contains only special characters.
    """
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")

    if not slug:
        return "untitled"

    if len(slug) <= max_len:
        return slug

    # Truncate at word boundary
    truncated = slug[:max_len]
    last_hyphen = truncated.rfind("-")
    if last_hyphen > 0:
        truncated = truncated[:last_hyphen]

    return truncated.rstrip("-")


def branch_name_from_ticket(
    ticket_id: str,
    title: str,
    labels: list[str],
) -> str:
    """Build a deterministic branch name from ticket metadata.

    Produces names in the format ``<type>/<TICKET_ID>-<slug>`` where
    *type* is derived from the ticket labels.

    Args:
        ticket_id: Ticket identifier (e.g. ``"AXM-42"``).
        title: Ticket title used to generate the slug.
        labels: Ticket labels used to determine the branch type.

    Returns:
        A URL-safe branch name.
    """
    branch_type = _resolve_type(labels)
    slug = slugify(title)
    return f"{branch_type}/{ticket_id}-{slug}"


def _resolve_type(labels: list[str]) -> str:
    """Map ticket labels to a branch type prefix.

    Uses a priority scan through *labels*: the first label found
    in :data:`LABEL_TO_TYPE` wins. Falls back to ``"feat"`` when
    no labels are provided, or ``"chore"`` when none match.
    """
    if not labels:
        return "feat"

    for label in labels:
        if label in LABEL_TO_TYPE:
            return LABEL_TO_TYPE[label]

    return "chore"
