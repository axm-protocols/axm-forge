"""Unit tests for score_impact with type refs (no I/O)."""

from __future__ import annotations

from typing import Any

from axm_ast.core.impact import score_impact


class TestImpactScoreUnit:
    """Pure dict-driven score_impact tests (no I/O)."""

    def test_impact_score_with_types(self) -> None:
        """AC3: Score is HIGH when type is used by 5+ functions."""
        result = {
            "callers": [],
            "reexports": [],
            "affected_modules": [],
            "git_coupled": [],
            "type_refs": [
                {"function": f"fn{i}", "module": "mod", "line": i} for i in range(5)
            ],
        }
        assert score_impact(result) == "HIGH"

    def test_score_medium_with_type_refs(self) -> None:
        """Score MEDIUM with 2 type refs and no callers."""
        result = {
            "callers": [],
            "reexports": [],
            "affected_modules": [],
            "git_coupled": [],
            "type_refs": [
                {"function": "fn1", "module": "mod", "line": 1},
                {"function": "fn2", "module": "mod", "line": 2},
            ],
        }
        assert score_impact(result) == "MEDIUM"

    def test_score_low_without_type_refs(self) -> None:
        """Score LOW with no type refs and no callers."""
        result: dict[str, Any] = {
            "callers": [],
            "reexports": [],
            "affected_modules": [],
            "git_coupled": [],
            "type_refs": [],
        }
        assert score_impact(result) == "LOW"
