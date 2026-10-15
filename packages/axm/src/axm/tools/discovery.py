"""Resolve the installed AXM tools from their entry-point groups (one resolver).

Every consumer that turns a tool name into an implementation goes through
:func:`tool_entry_points`: the MCP catalog (``axm_mcp.discovery``), the ``axm``
CLI (:mod:`axm.cli`) and :func:`axm.tools.load_tool` (hence every ``tool_node``).
They therefore never disagree on which distribution owns a name.

Resolution contract (axm-tribunal migration, decision "Groupes de points
d'entree", same rule as the graph and ticket-type groups):

* the groups are read in :data:`TOOL_ENTRY_POINT_GROUPS` order: the tribunal
  group ``axm.tribunal.tools`` first, the legacy ``axm.tools`` second;
* a name published by both groups resolves to the tribunal one. Publishing a
  tribunal homonym IS the switch away from a legacy tool; the shadowing is
  logged at debug level;
* a name published twice inside ONE group is ambiguous and raises
  :class:`DuplicateToolError` naming both distributions, instead of the old
  "last entry point wins" that depended on the filesystem order;
* the mapping is ordered by name, independent of ``sys.path`` or install order.

Python tool entry points are not loaded here; declarative providers additionally
read their installed package resource. No Svelte is compiled or evaluated.
Retiring the legacy group
(tribunal phase 10) is dropping ``"axm.tools"`` from the tuple.
"""

from __future__ import annotations

import importlib.metadata
import logging

from axm.tools.access import tool_is_allowed
from axm.tools.manifest_discovery import (
    DeclarativeToolReference,
    declarative_tool_references,
)

__all__ = [
    "TOOL_ENTRY_POINT_GROUPS",
    "DuplicateToolError",
    "ToolReference",
    "tool_entry_points",
]

type ToolReference = importlib.metadata.EntryPoint | DeclarativeToolReference

logger = logging.getLogger(__name__)

#: Entry-point groups AXM tools are published under, highest precedence first.
TOOL_ENTRY_POINT_GROUPS: tuple[str, ...] = ("axm.tribunal.tools", "axm.tools")


class DuplicateToolError(ValueError):
    """One entry-point group publishes the same tool name twice.

    Attributes:
        group: The entry-point group holding the two declarations.
        name: The tool name declared twice.
        distributions: The two declaring distributions, sorted.
    """

    def __init__(self, group: str, name: str, distributions: tuple[str, str]) -> None:
        self.group = group
        self.name = name
        self.distributions = distributions
        first, second = distributions
        super().__init__(
            f"tool {name!r} is published twice in entry-point group {group!r}, "
            f"by {first!r} and by {second!r}: a name has one owner per group"
        )


def tool_entry_points() -> dict[str, ToolReference]:
    """Map every installed AXM tool name to the entry point that owns it.

    Returns:
        ``{name: EntryPoint}`` sorted by name; a tribunal entry point shadows
        its legacy homonym. Python entries stay lazy; declarative resources
        are read and validated to publish their names and exact schemas.

    Raises:
        DuplicateToolError: One group publishes a name twice.
    """
    resolved: dict[str, ToolReference] = {}
    for group in TOOL_ENTRY_POINT_GROUPS:
        for name, ep in _group_entry_points(group).items():
            owner = resolved.setdefault(name, ep)
            if owner is not ep:
                logger.debug(
                    "tool %r: %s (%s) shadows %s (%s)",
                    name,
                    _distribution_name(owner),
                    owner.group,
                    _distribution_name(ep),
                    group,
                )
    for name, reference in declarative_tool_references().items():
        if name in resolved:
            raise ValueError(f"declarative tool collides with Python tool: {name}")
        resolved[name] = reference
    return {
        name: reference
        for name, reference in sorted(resolved.items())
        if tool_is_allowed(name)
    }


def _group_entry_points(group: str) -> dict[str, importlib.metadata.EntryPoint]:
    """The tools one group publishes, refusing a name declared twice."""
    published: dict[str, importlib.metadata.EntryPoint] = {}
    for ep in importlib.metadata.entry_points(group=group):
        previous = published.get(ep.name)
        if previous is not None:
            first, second = sorted(
                (_distribution_name(previous), _distribution_name(ep))
            )
            raise DuplicateToolError(group, ep.name, (first, second))
        published[ep.name] = ep
    return published


def _distribution_name(ep: ToolReference) -> str:
    """The distribution declaring *ep*, or its target when metadata lacks it."""
    if isinstance(ep, DeclarativeToolReference):
        return ep.value
    if ep.dist is not None:
        return str(ep.dist.name)
    return f"<unknown distribution of {ep.value}>"
