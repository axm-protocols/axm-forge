"""Unit tests for the paper checks module (pure front-matter parsing)."""

from __future__ import annotations

from axm_init.checks.paper import _PLAN_FILENAME, _parse_front_matter

FRONT_MATTER_DOC = """---
title: A Paper
status: draft
---

# Body
"""


def test_parse_front_matter_returns_the_declared_mapping() -> None:
    """AC3: a triple-dash delimited header parses into a mapping of its keys."""
    parsed = _parse_front_matter(FRONT_MATTER_DOC)

    assert parsed is not None
    assert parsed["title"] == "A Paper"
    assert parsed["status"] == "draft"


def test_parse_front_matter_returns_none_without_header() -> None:
    """AC3: plain prose carries no front-matter, so the parser returns None."""
    assert _parse_front_matter("# Plan\n\nJust prose, no header here.\n") is None


def test_plan_filename_is_the_canonical_uppercase_name() -> None:
    """AC1: the plan filename the check expects is exactly PLAN.md."""
    assert _PLAN_FILENAME == "PLAN.md"
