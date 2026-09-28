"""Composition families recognised by the protocol checks.

A protocol package composes its graph with one DAG authoring library and
publishes the factory under that library's entry-point group. While axm-loom
is being replaced by axm-tribunal, both families are recognised. Each family is
one row of :data:`COMPOSITION_FAMILIES`: retiring a family deletes its row and
nothing else, because every protocol check reads its names from this table.

Names are plain strings. axm-init never imports either library: calls are
resolved statically, through the inspected module's own imports.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "COMPOSITION_CALLS",
    "COMPOSITION_FAMILIES",
    "GRAPH_GROUPS",
    "CompositionFamily",
    "family_named",
    "family_of_protocol_call",
]


@dataclass(frozen=True, slots=True)
class CompositionFamily:
    """One DAG authoring library, described by the names the checks resolve.

    Attributes:
        name: Short family label used in findings (``"tribunal"``).
        graphs_group: Entry-point group its graph factories are published under.
        protocol_call: Qualified call whose first argument is the graph identity.
        calls: Qualified declarative composition calls, ``protocol_call``
            included; they are safe at module level in an inspected module.
    """

    name: str
    graphs_group: str
    protocol_call: str
    calls: frozenset[str]

    def __post_init__(self) -> None:
        """Refuse a row whose identity call is not one of its own calls."""
        if self.protocol_call not in self.calls:
            msg = f"{self.name}: protocol call {self.protocol_call!r} not in calls"
            raise ValueError(msg)


# Order is precedence: the first row is the target family, assumed when a
# protocol declares its identity without a resolvable composition call.
COMPOSITION_FAMILIES: tuple[CompositionFamily, ...] = (
    CompositionFamily(
        name="tribunal",
        graphs_group="axm.tribunal.graphs",
        protocol_call="axm_tribunal.protocol",
        calls=frozenset(
            {
                "axm_tribunal.ConfigTable",
                "axm_tribunal.evaluator.agent",
                "axm_tribunal.evaluator.deterministic",
                "axm_tribunal.phase",
                "axm_tribunal.protocol",
                "axm_tribunal.task.agent",
                "axm_tribunal.task.py",
            }
        ),
    ),
    # Legacy family: delete this row when axm-loom is retired.
    CompositionFamily(
        name="loom",
        graphs_group="axm.graphs",
        protocol_call="axm_loom.protocol",
        calls=frozenset(
            {
                "axm_loom.phase",
                "axm_loom.protocol",
                "axm_loom.router",
                "axm_loom.task",
            }
        ),
    ),
)

GRAPH_GROUPS: tuple[str, ...] = tuple(
    family.graphs_group for family in COMPOSITION_FAMILIES
)
"""Every recognised graph entry-point group, in family precedence order."""

COMPOSITION_CALLS: frozenset[str] = frozenset().union(
    *(family.calls for family in COMPOSITION_FAMILIES)
)
"""Every recognised declarative composition call, all families together."""


def family_of_protocol_call(qualified: str | None) -> CompositionFamily | None:
    """Return the family whose graph-identity call is *qualified*, if any."""
    return next((f for f in COMPOSITION_FAMILIES if f.protocol_call == qualified), None)


def family_named(name: str | None) -> CompositionFamily | None:
    """Return the family labelled *name*, if it is still recognised."""
    return next((f for f in COMPOSITION_FAMILIES if f.name == name), None)
