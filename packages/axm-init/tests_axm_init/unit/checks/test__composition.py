"""Unit tests for checks._composition — the composition family table."""

from __future__ import annotations

import pytest

from axm_init.checks._composition import (
    COMPOSITION_CALLS,
    COMPOSITION_FAMILIES,
    GRAPH_GROUPS,
    CompositionFamily,
    family_named,
    family_of_protocol_call,
)


def test_both_families_publish_under_distinct_groups() -> None:
    assert GRAPH_GROUPS == ("axm.tribunal.graphs", "axm.graphs")
    assert len({family.name for family in COMPOSITION_FAMILIES}) == len(
        COMPOSITION_FAMILIES
    )


@pytest.mark.parametrize(
    "call",
    [
        "axm_tribunal.task.agent",
        "axm_tribunal.task.py",
        "axm_tribunal.phase",
        "axm_tribunal.protocol",
        "axm_tribunal.evaluator.deterministic",
        "axm_tribunal.evaluator.agent",
        "axm_tribunal.ConfigTable",
        "axm_loom.task",
        "axm_loom.phase",
        "axm_loom.protocol",
        "axm_loom.router",
    ],
)
def test_recognises_every_family_call(call: str) -> None:
    assert call in COMPOSITION_CALLS


def test_tribunal_has_no_router() -> None:
    assert "axm_tribunal.router" not in COMPOSITION_CALLS


@pytest.mark.parametrize(
    ("call", "family"),
    [
        ("axm_tribunal.protocol", "tribunal"),
        ("axm_loom.protocol", "loom"),
        ("axm_tribunal.phase", None),
        ("unrelated.protocol", None),
        (None, None),
    ],
)
def test_family_of_protocol_call(call: str | None, family: str | None) -> None:
    found = family_of_protocol_call(call)
    assert (found.name if found else None) == family


def test_family_named_round_trips_every_row() -> None:
    for family in COMPOSITION_FAMILIES:
        assert family_named(family.name) is family
    assert family_named(None) is None
    assert family_named("retired") is None


def test_refuses_a_row_whose_identity_call_is_not_a_composition_call() -> None:
    with pytest.raises(ValueError, match="not in calls"):
        CompositionFamily(
            name="broken",
            graphs_group="axm.broken.graphs",
            protocol_call="broken.protocol",
            calls=frozenset({"broken.phase"}),
        )
