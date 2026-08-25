"""Integration test: compose the render primitives into a full compact text.

Also holds the *golden parity* suite: static fixtures captured from two distinct
canonical ``_render.py`` copies (``axm-backtest`` souche and ``axm-route`` travel
variant) are re-rendered through the ``axm_ingot.render`` primitives — composed
the way each copy's métier renderer would — and compared for exact equality. The
fixtures live under ``tests/fixtures/render/`` as static files; nothing is
imported from another workspace at test time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from axm_ingot.render import compact_table, header, labeled_block, truncate

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).parent.parent / "fixtures" / "render"


def _load(name: str) -> tuple[dict[str, Any], str]:
    payload = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return payload["input"], payload["expected"]


def render_backtest(p: dict[str, Any]) -> str:
    """Compose the ``axm-backtest`` souche shape from ingot primitives."""
    top = header(p["tool"], p["symbol"])
    summary = truncate(p["summary"], 60)
    metrics = labeled_block("Metrics", [f"{k}={v}" for k, v in p["metrics"].items()])
    trades = compact_table(
        [[t["date"], t["side"], t["qty"], t["price"]] for t in p["trades"]],
        headers=["date", "side", "qty", "price"],
    )
    return "\n".join([top, summary, metrics, trades])


def render_route(p: dict[str, Any]) -> str:
    """Compose the ``axm-route`` travel variant shape from ingot primitives."""
    top = header(p["tool"], f"{p['origin']}→{p['destination']}")
    legs = compact_table(
        [[leg["from"], leg["to"], leg["km"], leg["eta"]] for leg in p["legs"]],
        headers=["from", "to", "km", "eta"],
    )
    notes = labeled_block("Notes", [truncate(p["notes"], 50)])
    return "\n".join([top, legs, notes])


def test_full_compact_text_assembled_from_composed_primitives() -> None:
    summary = truncate("audited 3 files, 2 findings across the workspace", 60)
    top = header("audit", summary)
    block = labeled_block("Findings", ["complexity: 1", "security: 1"])
    table = compact_table(
        [["src/a.py", "complexity"], ["src/b.py", "security"]],
        headers=["file", "rule"],
    )
    text = "\n".join([top, block, table])

    lines = text.splitlines()
    assert lines[0] == top
    assert text.index("Findings") < text.index("src/a.py")
    assert "src/a.py" in text
    assert "file" in text and "rule" in text
    assert text.startswith("audit | ")


def test_golden_parity_backtest_souche_copy() -> None:
    payload, expected = _load("backtest_result")
    assert render_backtest(payload) == expected


def test_golden_parity_route_travel_variant_copy() -> None:
    payload, expected = _load("route_result")
    assert render_route(payload) == expected


def test_golden_parity_fails_under_noop_truncate_primitive() -> None:
    # Behavioral guard: the golden captured a truncated ``notes`` field. An
    # identity (no-op) ``truncate`` would leak the full string, so the full
    # untruncated notes must NOT survive into the rendered/golden output.
    payload, expected = _load("route_result")
    full_notes = payload["notes"]

    assert len(full_notes) > 50
    assert full_notes not in expected
    assert expected == render_route(payload)
    assert "possibl…" in expected  # truncated marker present, not the full word
