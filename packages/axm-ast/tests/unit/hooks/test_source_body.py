from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest


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
