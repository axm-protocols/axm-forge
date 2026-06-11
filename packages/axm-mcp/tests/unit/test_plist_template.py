"""Unit tests for :mod:`axm_mcp.plist_template`."""

from __future__ import annotations

from axm_mcp.plist_template import PLIST_TEMPLATE


class TestPlistTemplate:
    """The launchd plist template must format with the documented fields."""

    def test_template_formats_all_placeholders(self) -> None:
        """All four placeholders are substituted into the rendered plist."""
        rendered = PLIST_TEMPLATE.format(
            bin_path="/usr/local/bin/axm-mcp",
            port="9427",
            log_dir="/var/log/axm",
        )

        assert "<string>/usr/local/bin/axm-mcp</string>" in rendered
        assert "<string>9427</string>" in rendered
        assert "<string>/var/log/axm/stdout.log</string>" in rendered
        assert "<string>/var/log/axm/stderr.log</string>" in rendered

    def test_template_has_no_unsubstituted_braces(self) -> None:
        """After formatting, no `{placeholder}` markers remain."""
        rendered = PLIST_TEMPLATE.format(
            bin_path="/bin/axm-mcp", port="8080", log_dir="/tmp/logs"
        )

        assert "{" not in rendered
        assert "}" not in rendered

    def test_template_is_valid_launchd_plist(self) -> None:
        """Rendered output parses as a launchd plist with the expected label."""
        import plistlib

        rendered = PLIST_TEMPLATE.format(
            bin_path="/bin/axm-mcp", port="9427", log_dir="/tmp/logs"
        )
        parsed = plistlib.loads(rendered.encode())

        assert parsed["Label"] == "io.axm.mcp-server"
        assert parsed["ProgramArguments"][0] == "/bin/axm-mcp"
        assert parsed["KeepAlive"] is True
        assert parsed["RunAtLoad"] is True
