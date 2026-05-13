"""Integration tests for analyze_impact_workspace end-to-end behavior."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.mark.usefixtures("_mock_analyze_workspace")
class TestAnalyzeImpactWorkspace:
    """Verify analyze_impact_workspace output is unchanged after refactor."""

    def test_analyze_impact_workspace(self, workspace_path: Path) -> None:
        from axm_ast.core.impact import analyze_impact_workspace

        result = analyze_impact_workspace(workspace_path, "MySymbol")

        assert result["symbol"] == "MySymbol"
        assert result["workspace"] == "my-ws"
        assert "definition" in result
        assert "callers" in result
        assert "reexports" in result
        assert "affected_modules" in result
        assert "test_files" in result
        assert "score" in result

    def test_missing_workspace_root(self, tmp_path: Path) -> None:
        """analyze_impact_workspace with invalid path → graceful empty result."""
        from axm_ast.core.impact import analyze_impact_workspace

        invalid = tmp_path / "nonexistent"
        result = analyze_impact_workspace(invalid, "Foo")

        # Graceful: returns a valid dict with empty collections
        assert result["symbol"] == "Foo"
        assert isinstance(result["callers"], list)
        assert isinstance(result["score"], str)


@pytest.fixture()
def workspace_path(tmp_path: Path) -> Path:
    """Return a dummy workspace path for testing."""
    return tmp_path / "ws"


@pytest.fixture()
def _mock_analyze_workspace(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock analyze_workspace and its transitive deps for unit tests."""
    pkg = MagicMock()
    pkg.name = "my-pkg"
    ws = MagicMock()
    ws.name = "my-ws"
    ws.packages = [pkg]

    mock_aw = MagicMock(return_value=ws)
    monkeypatch.setattr(
        "axm_ast.core.impact.analyze_workspace",
        mock_aw,
    )

    # find_definition returns a simple dict
    monkeypatch.setattr(
        "axm_ast.core.impact.find_definition",
        MagicMock(return_value={"module": "mod", "line": 1}),
    )
    monkeypatch.setattr(
        "axm_ast.core.impact.find_callers_workspace",
        MagicMock(return_value=[]),
    )
    monkeypatch.setattr(
        "axm_ast.core.impact._collect_workspace_reexports",
        MagicMock(return_value=[]),
    )
    monkeypatch.setattr(
        "axm_ast.core.impact._collect_workspace_tests",
        MagicMock(return_value=[]),
    )
    monkeypatch.setattr(
        "axm_ast.core.impact._add_workspace_git_coupling",
        MagicMock(),
    )
    monkeypatch.setattr(
        "axm_ast.core.impact.score_impact",
        MagicMock(return_value="LOW"),
    )
    return mock_aw
