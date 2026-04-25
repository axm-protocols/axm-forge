"""Tests for CLI (cyclopts)."""

import pytest


class TestCLI:
    """Tests for CLI commands."""

    def test_version_command(self, capsys: pytest.CaptureFixture[str]) -> None:
        """version command should print the package version to stdout."""
        from axm_audit import __version__
        from axm_audit.cli import version

        version()
        out = capsys.readouterr().out
        assert __version__ in out
        assert "axm-audit" in out

    def test_agent_flag_exists(self) -> None:
        """--agent flag should be accepted by audit command."""
        import inspect

        from axm_audit.cli import audit

        sig = inspect.signature(audit)
        assert "agent" in sig.parameters


# Test-failure extraction is exercised end-to-end through ``CoverageRule().check()``
# in ``tests/integration/test_coverage_rule_e2e.py``.
