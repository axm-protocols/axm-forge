"""Parity: the preflight blocks a replace iff the engine would refuse it.

Both layers resolve anchors through ``core.anchor_match``; this suite pins
that contract on real files, so a future matching rule added to one layer
only fails here instead of silently diverging.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import pytest

from axm_edit.core.engine import batch_apply
from axm_edit.core.preflight import collect_preflight_diagnostics
from axm_edit.models.operations import Edit, ReplaceOp

pytestmark = pytest.mark.integration

SRC = (
    "def f():\n"
    '    msg = "hello"\n'
    "    return 1\n"
    "\n"
    "\n"
    "def g():\n"
    "    xx = 1\n"
    "    return 1\n"
)
NBSP = chr(0xA0)
LEFT, RIGHT = chr(0x201C), chr(0x201D)


class Case(NamedTuple):
    """One replace scenario and the engine's expected verdict."""

    id: str
    name: str
    content: str
    old: str
    new: str
    line: int | None
    accepted: bool


CASES: list[Case] = [
    Case("exact", "m.py", SRC, "    xx = 1", "    xx = 2", None, True),
    Case(
        "smart-quotes",
        "m.py",
        SRC,
        f"    msg = {LEFT}hello{RIGHT}",
        '    msg = "bye"',
        None,
        True,
    ),
    Case("missing-indent", "m.py", SRC, 'msg = "hello"', 'msg = "bye"', None, True),
    Case("line-substring", "m.py", SRC, "x = 1", "x = 2", None, False),
    Case("ambiguous-hinted", "m.py", SRC, "    return 1", "    return 2", 8, True),
    Case("ambiguous", "m.py", SRC, "    return 1", "    return 2", None, False),
    Case(
        "multi-line",
        "m.py",
        SRC,
        "def g():\n    xx = 1",
        "def g():\n    xx = 2",
        None,
        True,
    ),
    Case("multi-line-mid-line", "m.py", SRC, "f():\n    msg", "g", None, False),
    Case("stale-hint", "m.py", SRC, "    xx = 1", "    xx = 2", 1, True),
    Case("over-escaped", "m.py", SRC, '    msg = \\"hello\\"', "    pass", None, False),
    Case("wrapping-quotes", "m.py", SRC, '"    xx = 1"', "    xx = 2", None, True),
    Case("nbsp", "m.py", SRC, f"    xx{NBSP}= 1", "    xx = 2", None, False),
    Case(
        "form-feed",
        "m.txt",
        "alpha\x0cbeta\ngamma\n",
        "alpha\x0cbeta",
        "delta",
        None,
        True,
    ),
    Case(
        "crlf",
        "m.py",
        SRC.replace("\n", "\r\n"),
        "    xx = 1",
        "    xx = 2",
        None,
        True,
    ),
    Case("no-final-newline", "m.py", "a = 1\nb = 2", "b = 2", "b = 3", None, True),
]


@pytest.mark.parametrize("case", CASES, ids=[case.id for case in CASES])
def test_preflight_blocks_exactly_what_the_engine_refuses(
    tmp_path: Path, case: Case
) -> None:
    """Preflight blocking and engine refusal agree, case by case."""
    (tmp_path / case.name).write_bytes(case.content.encode("utf-8"))
    edit: dict[str, object] = {"old": case.old, "new": case.new}
    if case.line is not None:
        edit["line"] = case.line
    raw = [{"op": "replace", "file": case.name, "edits": [edit]}]

    diagnostics = collect_preflight_diagnostics(tmp_path, raw)
    blocked = any(d.severity == "error" for d in diagnostics)
    replace = ReplaceOp(
        file=case.name, edits=[Edit(old=case.old, new=case.new, line=case.line)]
    )
    result = batch_apply(tmp_path, [replace])

    assert result.success is case.accepted, result.details
    assert blocked is not case.accepted, diagnostics


def test_normalized_match_is_accepted_with_a_warning(tmp_path: Path) -> None:
    """A smart-quote anchor passes, flagged as a normalized guess."""
    (tmp_path / "m.py").write_text(SRC, encoding="utf-8")
    old = f"    msg = {LEFT}hello{RIGHT}"
    raw = [
        {"op": "replace", "file": "m.py", "edits": [{"old": old, "new": "    pass"}]}
    ]

    diagnostics = collect_preflight_diagnostics(tmp_path, raw)

    assert [(d.severity, d.code) for d in diagnostics] == [
        ("warning", "ANCHOR_NORMALIZED")
    ]
    assert "smart quotes" in diagnostics[0].message
    assert "line 2" in diagnostics[0].message
