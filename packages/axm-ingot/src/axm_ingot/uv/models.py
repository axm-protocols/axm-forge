"""Frozen value types for resolved uv workspaces.

STDLIB only (``dataclasses`` + ``pathlib``); axm-ingot stays a leaf of the
forge dependency graph -- no Pydantic, no ``axm_*`` import.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = ["Member", "ResolvedWorkspace"]


@dataclass(frozen=True)
class Member:
    """A single uv-workspace member.

    Attributes:
        name: Directory name of the member.
        path: Absolute, resolved path to the member directory.
    """

    name: str
    path: Path


@dataclass(frozen=True)
class ResolvedWorkspace:
    """A uv workspace with its resolved members.

    Attributes:
        root: Absolute path to the workspace root (holding the root pyproject).
        members: Members sorted by name.
    """

    root: Path
    members: tuple[Member, ...]
