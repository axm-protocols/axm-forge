"""Split from ``test_git_coupling.py``."""

from pathlib import Path

from axm_ast.core.impact import score_impact


def test_impact_score_with_coupling(tmp_path: Path) -> None:
    """Coupling increases impact score vs without."""
    from axm_ast.core.impact import score_impact

    # Without coupling
    result_no_coupling: dict[str, object] = {
        "callers": [],
        "reexports": [],
        "affected_modules": [],
        "git_coupled": [],
    }
    score_without = score_impact(result_no_coupling)

    # With coupling (3 coupled files)
    result_with_coupling: dict[str, object] = {
        "callers": [],
        "reexports": [],
        "affected_modules": [],
        "git_coupled": [
            {"file": "a.py", "strength": 0.8, "co_changes": 10},
            {"file": "b.py", "strength": 0.5, "co_changes": 5},
            {"file": "c.py", "strength": 0.4, "co_changes": 4},
        ],
    }
    score_with = score_impact(result_with_coupling)

    # Score should be higher with coupling
    levels = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    assert levels[score_with] > levels[score_without]


class TestScoreImpactFromDict:
    """Test impact scoring."""

    def test_high_impact(self) -> None:
        """Many callers + re-exported = HIGH."""
        result = {
            "callers": [1, 2, 3, 4, 5],
            "reexports": ["__init__"],
            "affected_modules": ["a", "b", "c"],
        }
        assert score_impact(result) == "HIGH"

    def test_low_impact(self) -> None:
        """No callers, no re-exports = LOW."""
        result: dict[str, list[str | int]] = {
            "callers": [],
            "reexports": [],
            "affected_modules": [],
        }
        assert score_impact(result) == "LOW"

    def test_medium_impact(self) -> None:
        """Some callers = MEDIUM."""
        result = {
            "callers": [1, 2],
            "reexports": [],
            "affected_modules": ["a"],
        }
        assert score_impact(result) == "MEDIUM"
