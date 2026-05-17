"""Split from ``test_source_body.py``."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from axm_ast.hooks.source_body import SourceBodyHook
from axm_ast.models.nodes import (
    VariableInfo,
)
from tests.integration._helpers import _ANALYZER, _make_mock_mod


class TestSourceBodyVariable:
    """Variable/constant resolution in source_body hook."""

    @patch(f"{_ANALYZER}.find_module_for_symbol")
    @patch(f"{_ANALYZER}.search_symbols")
    @patch(f"{_ANALYZER}.analyze_package")
    def test_source_body_resolves_variable(
        self,
        mock_analyze: MagicMock,
        mock_search: MagicMock,
        mock_find: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Returns file, line, value_repr, body for a module-level constant."""

        src = tmp_path / "consts.py"
        src.write_text("_TOLERANCE: float = 0.01\nMAX = 100\n")

        mock_var = VariableInfo(
            name="_TOLERANCE", annotation="float", value_repr="0.01", line=1
        )

        mock_mod = MagicMock()
        mock_mod.path = src

        mock_pkg = MagicMock()
        mock_analyze.return_value = mock_pkg
        mock_search.return_value = [("consts", mock_var)]
        mock_find.return_value = mock_mod

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="_TOLERANCE", path=str(tmp_path))

        assert result.success
        data = result.metadata["symbols"]
        assert isinstance(data, str)
        assert "consts.py" in data
        assert "_TOLERANCE" in data
        assert "value_repr" in data or "0.01" in data
        assert "```python" in data


class TestVariableSymbolIncludesRepr:
    """Variable symbols include value_repr in output."""

    @patch(f"{_ANALYZER}.find_module_for_symbol")
    @patch(f"{_ANALYZER}.search_symbols")
    @patch(f"{_ANALYZER}.analyze_package")
    def test_variable_symbol_includes_repr(
        self,
        mock_analyze: MagicMock,
        mock_search: MagicMock,
        mock_find: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Variable extraction includes value_repr in the markdown output."""

        src = tmp_path / "consts.py"
        src.write_text("MAX_RETRIES: int = 3\n")

        mock_var = VariableInfo(
            name="MAX_RETRIES", annotation="int", value_repr="3", line=1
        )
        mock_mod = _make_mock_mod(src)
        mock_analyze.return_value = MagicMock()
        mock_search.return_value = [("consts", mock_var)]
        mock_find.return_value = mock_mod

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="MAX_RETRIES", path=str(tmp_path))

        assert result.success
        symbols = result.metadata["symbols"]
        assert isinstance(symbols, str)
        assert "value_repr" in symbols or "3" in symbols
