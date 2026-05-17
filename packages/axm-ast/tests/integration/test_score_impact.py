"""Split from ``test_git_coupling.py``."""

from pathlib import Path

from axm_ast.core.impact import score_impact


def test_impact_score_with_coupling(tmp_path: Path) -> None:
    """Coupling increases impact score vs without."""

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
