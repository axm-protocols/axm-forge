from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Functional / regression tests
# ---------------------------------------------------------------------------


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


class TestSourceBodySingleSymbol:
    """Single symbol hook call → same body extraction."""

    def test_source_body_single_symbol(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from axm_ast.hooks.source_body import SourceBodyHook

        # Create a minimal source file so analyze_package can work
        # We mock analyze_package instead
        mock_pkg = MagicMock()
        monkeypatch.setattr(
            "axm_ast.hooks.source_body.analyze_package",
            MagicMock(return_value=mock_pkg),
        )
        monkeypatch.setattr(
            "axm_ast.hooks.source_body._extract_symbol",
            MagicMock(
                return_value={
                    "symbol": "foo",
                    "file": "src/mod.py",
                    "start_line": 1,
                    "end_line": 5,
                    "body": "def foo(): pass",
                }
            ),
        )

        hook = SourceBodyHook()
        result = hook.execute(
            context={"working_dir": str(tmp_path)},
            symbol="foo",
        )

        assert result.success is True
        assert isinstance(result.metadata["symbols"], str)
        assert "def foo(): pass" in result.metadata["symbols"]


class TestSourceBodyDottedClassMethod:
    """Dotted Class.method resolution → same result."""

    def test_source_body_dotted_class_method(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from axm_ast.hooks.source_body import _resolve_as_class_method

        mock_cls = MagicMock()
        mock_cls.name = "MyClass"
        mock_cls.methods = [MagicMock(name="my_method", line_start=10, line_end=20)]
        # Fix: MagicMock.name is special, set it explicitly
        mock_cls.methods[0].name = "my_method"

        mock_mod = MagicMock()
        mock_mod.path = Path("/root/src/mod.py")

        monkeypatch.setattr(
            "axm_ast.hooks.source_body.search_symbols",
            MagicMock(return_value=[("mod", mock_cls)]),
        )
        monkeypatch.setattr(
            "axm_ast.hooks.source_body.find_module_for_symbol",
            MagicMock(return_value=mock_mod),
        )
        monkeypatch.setattr(
            "axm_ast.hooks.source_body._read_body",
            MagicMock(return_value="def my_method(): pass"),
        )

        result = _resolve_as_class_method(
            pkg=MagicMock(),
            class_name="MyClass",
            member_name="my_method",
            symbol_name="MyClass.my_method",
            pkg_root=Path("/root"),
        )

        assert result is not None
        assert result["symbol"] == "MyClass.my_method"
        assert result["start_line"] == 10
        assert result["end_line"] == 20

    def test_unknown_dotted_symbol(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_resolve_as_class_method with non-existent class → None."""
        from axm_ast.hooks.source_body import _resolve_as_class_method

        monkeypatch.setattr(
            "axm_ast.hooks.source_body.search_symbols",
            MagicMock(return_value=[]),
        )

        result = _resolve_as_class_method(
            pkg=MagicMock(),
            class_name="NonExistent",
            member_name="method",
            symbol_name="NonExistent.method",
            pkg_root=Path("/root"),
        )

        assert result is None
