"""Shared entry-point discovery for ``axm.tools`` consumers.

A single module-level helper so the CLI (``axm.cli``) and the DAG node adapter
(``axm.tools.node``) discover entry points the exact same way — one metadata
query, one ``{name: EntryPoint}`` mapping, no duplicated ``entry_points(...)``
call drifting between the two. Kept inside ``axm.tools`` so ``node.py`` imports
it as a sibling and ``cli.py`` imports it from the package (the dependency
direction already in use), with no import cycle.
"""

from __future__ import annotations

import importlib.metadata

__all__ = ["entry_points_for"]


def entry_points_for(group: str) -> dict[str, importlib.metadata.EntryPoint]:
    """Map name -> entry point for *group* (no ``.load()`` — pure metadata)."""
    return {ep.name: ep for ep in importlib.metadata.entry_points(group=group)}
