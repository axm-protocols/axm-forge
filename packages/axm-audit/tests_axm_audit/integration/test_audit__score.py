"""Integration: the audit JSON surface always carries a numeric ``.score``.

Exercises the real ``audit_project`` entrypoint feeding ``format_json``, and
asserts the JSON payload's score/grade come from the single serialization
source (``resolve_score_grade``) — no divergent computation, no dropped key.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.auditor import audit_project
from axm_audit.formatters import format_json
from axm_audit.score import resolve_score_grade

pytestmark = pytest.mark.integration

_GRADES = {"A", "B", "C", "D", "F"}


def _scaffold(root: Path) -> None:
    src = root / "src" / "sample_pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "core.py").write_text("def add(a: int, b: int) -> int:\n    return a + b\n")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "sample-pkg"\nversion = "0.0.1"\n'
        'requires-python = ">=3.12"\n'
    )


def test_audit_json_over_fixture_always_carries_numeric_score(tmp_path: Path) -> None:
    """AC1/AC3: format_json over a real audit carries a numeric ``.score`` that
    equals the single serialization source's output."""
    _scaffold(tmp_path)
    result = audit_project(tmp_path, category="lint")

    payload = format_json(result)

    assert isinstance(payload["score"], int | float)
    assert payload["grade"] in _GRADES

    # AC3: format_json's (score, grade) is exactly what the single source emits.
    score, grade = resolve_score_grade(result)
    assert payload["score"] == score
    assert payload["grade"] == grade
