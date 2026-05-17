"""Split from ``test_context.py``."""

from unittest.mock import patch

from axm_ast.core.context import detect_axm_tools


class TestDetectAxmTools:
    """Test AXM ecosystem tool detection."""

    def test_detect_axm_tools_available(self) -> None:
        """Finds installed AXM tools."""
        with patch("shutil.which", return_value="/usr/bin/axm-ast"):
            tools = detect_axm_tools()
        assert "axm-ast" in tools

    def test_detect_axm_tools_missing(self) -> None:
        """Missing tools are not included."""
        with patch("shutil.which", return_value=None):
            tools = detect_axm_tools()
        assert tools == {}

    def test_detect_axm_tools_partial(self) -> None:
        """Only installed tools are returned."""

        def _mock_which(name: str) -> str | None:
            return "/usr/bin/" + name if name == "axm-ast" else None

        with patch("shutil.which", side_effect=_mock_which):
            tools = detect_axm_tools()
        assert "axm-ast" in tools
        assert "axm-audit" not in tools
