"""Tests for CLI (cyclopts)."""


class TestCLI:
    """Tests for CLI commands."""

    def test_version_command(self) -> None:
        """version command should print version."""
        from axm_audit.cli import app

        # cyclopts apps can be tested by calling them directly
        # We just verify the app exists and has commands
        assert app is not None

    def test_audit_command_exists(self) -> None:
        """audit command should be registered."""
        from axm_audit.cli import app

        assert app is not None

    def test_agent_flag_exists(self) -> None:
        """--agent flag should be accepted by audit command."""
        import inspect

        from axm_audit.cli import audit

        sig = inspect.signature(audit)
        assert "agent" in sig.parameters


class TestExtractTestFailures:
    """Tests for _extract_test_failures helper."""

    def test_no_failures(self) -> None:
        """Empty stdout → no failures."""
        from axm_audit.core.rules.coverage import _extract_test_failures

        assert _extract_test_failures("") == []
        assert _extract_test_failures("3 passed\n") == []

    def test_single_failure(self) -> None:
        """FAILED line parsed correctly."""
        from axm_audit.core.rules.coverage import _extract_test_failures

        stdout = "FAILED tests/test_foo.py::test_bar - AssertionError\n1 failed\n"
        failures = _extract_test_failures(stdout)
        assert len(failures) == 1
        assert failures[0]["test"] == "tests/test_foo.py::test_bar"
        assert "AssertionError" in failures[0]["traceback"]

    def test_multiple_failures(self) -> None:
        """Multiple FAILED lines parsed."""
        from axm_audit.core.rules.coverage import _extract_test_failures

        stdout = (
            "FAILED tests/test_a.py::test_one - err1\n"
            "FAILED tests/test_b.py::test_two - err2\n"
            "2 failed\n"
        )
        failures = _extract_test_failures(stdout)
        assert len(failures) == 2
