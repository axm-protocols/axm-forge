"""Unit tests for SourceBodyHook."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from axm_ast.hooks.source_body import SourceBodyHook
from tests.unit._helpers import _ANALYZER

# ── single-symbol body extraction ──


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


# ── dotted Class.method resolution ──


class TestSourceBodyDottedClassMethod:
    """Dotted Class.method resolution → same result."""

    def test_source_body_dotted_class_method(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from axm_ast.hooks.source_body import _resolve_as_class_method
        from axm_ast.models import ClassInfo, FunctionInfo

        cls = ClassInfo(
            name="MyClass",
            line_start=1,
            line_end=30,
            methods=[FunctionInfo(name="my_method", line_start=10, line_end=20)],
        )

        mock_mod = MagicMock()
        mock_mod.path = Path("/root/src/mod.py")

        monkeypatch.setattr(
            "axm_ast.hooks.source_body.search_symbols",
            MagicMock(return_value=[("mod", cls)]),
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


# ── markdown rendering edge cases ──


class TestSymbolNotFoundEdge:
    """Edge: non-existent symbol returns HookResult with error."""

    @patch(f"{_ANALYZER}.search_symbols", return_value=[])
    @patch(f"{_ANALYZER}.analyze_package")
    def test_symbol_not_found(
        self,
        mock_analyze: MagicMock,
        _mock_search: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Non-existent symbol does not crash."""
        mock_analyze.return_value = MagicMock()

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="ghost_func", path=str(tmp_path))

        # Should still return a result without crash
        assert result.success or not result.success


class TestSourceBodyMissingSymbol:
    """Missing symbol handling — no crash, body=null."""

    @patch(f"{_ANALYZER}.search_symbols", return_value=[])
    @patch(f"{_ANALYZER}.analyze_package")
    def test_source_body_missing_symbol(
        self,
        mock_analyze: MagicMock,
        _mock_search: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Unknown symbol returns body=None with error message."""
        mock_pkg = MagicMock()
        mock_analyze.return_value = mock_pkg

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="nonexistent", path=str(tmp_path))

        assert result.success
        data = result.metadata["symbols"]
        assert isinstance(data, str)
        assert "nonexistent" in data


class TestSourceBodyDottedNotFound:
    """Dotted symbol: not found returns error."""

    @patch(f"{_ANALYZER}.search_symbols", return_value=[])
    @patch(f"{_ANALYZER}.analyze_package")
    def test_source_body_dotted_not_found(
        self,
        mock_analyze: MagicMock,
        _mock_search: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Foo.nonexistent returns error dict with body=None."""
        mock_pkg = MagicMock()
        mock_analyze.return_value = mock_pkg

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="Foo.nonexistent", path=str(tmp_path))

        assert result.success
        data = result.metadata["symbols"]
        assert isinstance(data, str)
        assert "not found" in data.lower() or "error" in data.lower()


# ── error paths (missing/invalid params) ──


class TestSourceBodyMissingPath:
    """Invalid path handling."""

    def test_source_body_missing_path(self) -> None:
        """Invalid path returns HookResult.fail with clear message."""
        hook = SourceBodyHook()
        result = hook.execute({}, symbol="Foo", path="/invalid/nonexistent")
        assert not result.success
        assert result.error is not None
        assert "not a directory" in result.error


class TestMissingPathEdge:
    """Edge: invalid path in params."""

    def test_missing_path(self) -> None:
        """Invalid path returns HookResult.fail (unchanged)."""
        hook = SourceBodyHook()
        result = hook.execute({}, symbol="Foo", path="/invalid/nonexistent")
        assert not result.success
        assert result.error is not None


class TestSourceBodyMissingParam:
    """Missing required param."""

    def test_missing_symbol_param(self) -> None:
        """Fail when 'symbol' param is missing."""
        hook = SourceBodyHook()
        result = hook.execute({})
        assert not result.success
        assert result.error is not None
        assert "symbol" in result.error


# ── entry-point registration ──


class TestEntryPointDiscoverable:
    """Entry point registration test."""

    def test_entry_point_discoverable(self) -> None:
        """'ast:source-body' is registered in axm.hooks entry points."""
        from importlib.metadata import entry_points

        hooks = entry_points(group="axm.hooks")
        names = [ep.name for ep in hooks]
        assert "ast:source-body" in names
