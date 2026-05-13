"""Tests for tools.reserve — test mirror."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestReserveToolValidation:
    """Validate required kwargs handling."""

    def test_missing_name_returns_error(self) -> None:
        """Calling execute() without 'name' returns a ToolResult error."""
        from axm_init.tools.reserve import InitReserveTool

        tool = InitReserveTool()
        result = tool.execute()
        assert result.success is False
        assert "'name' is required" in (result.error or "")

    def test_tool_rejects_empty_author(self) -> None:
        """Empty author returns error."""
        from axm_init.tools.reserve import InitReserveTool

        tool = InitReserveTool()
        result = tool.execute(name="test-pkg", author="", email="a@b.com")
        assert result.success is False
        assert "author" in (result.error or "").lower()

    def test_tool_rejects_placeholder_author(self) -> None:
        """Placeholder 'John Doe' author returns error."""
        from axm_init.tools.reserve import InitReserveTool

        tool = InitReserveTool()
        result = tool.execute(
            name="test-pkg", author="John Doe", email="real@email.com"
        )
        assert result.success is False
        assert "placeholder" in (result.error or "").lower()

    def test_tool_rejects_empty_email(self) -> None:
        """Empty email returns error."""
        from axm_init.tools.reserve import InitReserveTool

        tool = InitReserveTool()
        result = tool.execute(name="test-pkg", author="Real Author", email="")
        assert result.success is False
        assert "email" in (result.error or "").lower()

    def test_tool_rejects_placeholder_email(self) -> None:
        """Placeholder email returns error."""
        from axm_init.tools.reserve import InitReserveTool

        tool = InitReserveTool()
        result = tool.execute(
            name="test-pkg",
            author="Real Author",
            email="john.doe@example.com",
        )
        assert result.success is False
        assert "placeholder" in (result.error or "").lower()

    @patch("axm_init.core.reserver.reserve_pypi")
    @patch("axm_init.adapters.credentials.CredentialManager")
    def test_reserve_success(
        self, mock_creds: MagicMock, mock_reserve: MagicMock
    ) -> None:
        """Test successful execution of InitReserveTool."""
        from axm_init.models.results import ReserveResult
        from axm_init.tools.reserve import InitReserveTool

        mock_creds.return_value.get_pypi_token.return_value = "fake-token"
        mock_reserve.return_value = ReserveResult(
            success=True,
            package_name="test-package",
            version="0.1.0",
            message="Reserved test-package",
        )
        tool = InitReserveTool()
        result = tool.execute(
            name="test-package", author="Author", email="email@test.com"
        )
        assert result.success is True

    @patch("axm_init.core.reserver.reserve_pypi")
    @patch("axm_init.adapters.credentials.CredentialManager")
    def test_reserve_failure(
        self, mock_creds: MagicMock, mock_reserve: MagicMock
    ) -> None:
        """Test failed execution of InitReserveTool."""
        from axm_init.models.results import ReserveResult
        from axm_init.tools.reserve import InitReserveTool

        mock_creds.return_value.get_pypi_token.return_value = "fake-token"
        mock_reserve.return_value = ReserveResult(
            success=False,
            package_name="test-package",
            version="",
            message="Package name taken",
        )
        tool = InitReserveTool()
        result = tool.execute(
            name="test-package", author="Author", email="email@test.com"
        )
        assert result.success is False

    @patch("axm_init.adapters.credentials.CredentialManager")
    def test_reserve_system_exit_caught(self, mock_creds: MagicMock) -> None:
        """Test InitReserveTool catches exceptions."""
        from axm_init.tools.reserve import InitReserveTool

        mock_creds.return_value.get_pypi_token.side_effect = Exception(
            "SystemExit error"
        )
        tool = InitReserveTool()
        result = tool.execute(
            name="test-package", author="Author", email="email@test.com"
        )
        assert result.success is False
        assert result.error and (
            "SystemExit" in result.error or "Error" in result.error
        )


# --- merged from test_reserve_coverage.py ---


class TestReserveNoToken:
    """Cover lines 73-78: no PyPI token when not in dry_run."""

    @patch("axm_init.adapters.credentials.CredentialManager")
    def test_no_token_returns_error(self, mock_creds: MagicMock) -> None:
        """No PyPI token found → ToolResult(success=False)."""
        from axm_init.tools.reserve import InitReserveTool

        mock_creds.return_value.get_pypi_token.return_value = None
        tool = InitReserveTool()
        result = tool.execute(
            name="test-pkg",
            author="Real Author",
            email="real@email.com",
        )
        assert result.success is False
        assert "No PyPI token" in (result.error or "")


class TestReserveDryRun:
    """Cover line 80: dry_run path where token may be None."""

    @patch("axm_init.core.reserver.reserve_pypi")
    @patch("axm_init.adapters.credentials.CredentialManager")
    def test_dry_run_no_token_uses_empty(
        self, mock_creds: MagicMock, mock_reserve: MagicMock
    ) -> None:
        """dry_run=True with no token uses empty string."""
        from axm_init.models.results import ReserveResult
        from axm_init.tools.reserve import InitReserveTool

        mock_creds.return_value.get_pypi_token.return_value = None
        mock_reserve.return_value = ReserveResult(
            success=True,
            package_name="test-pkg",
            version="0.0.1",
            message="Dry run OK",
        )
        tool = InitReserveTool()
        result = tool.execute(
            name="test-pkg",
            author="Real Author",
            email="real@email.com",
            dry_run=True,
        )
        assert result.success is True
        mock_reserve.assert_called_once_with(
            name="test-pkg",
            author="Real Author",
            email="real@email.com",
            token="",
            dry_run=True,
        )

    @patch("axm_init.core.reserver.reserve_pypi")
    @patch("axm_init.adapters.credentials.CredentialManager")
    def test_dry_run_with_token(
        self, mock_creds: MagicMock, mock_reserve: MagicMock
    ) -> None:
        """dry_run=True with existing token passes token through."""
        from axm_init.models.results import ReserveResult
        from axm_init.tools.reserve import InitReserveTool

        mock_creds.return_value.get_pypi_token.return_value = "real-token"
        mock_reserve.return_value = ReserveResult(
            success=True,
            package_name="test-pkg",
            version="0.0.1",
            message="Dry run OK",
        )
        tool = InitReserveTool()
        result = tool.execute(
            name="test-pkg",
            author="Real Author",
            email="real@email.com",
            dry_run=True,
        )
        assert result.success is True
        mock_reserve.assert_called_once_with(
            name="test-pkg",
            author="Real Author",
            email="real@email.com",
            token="real-token",
            dry_run=True,
        )


class TestReserveNameProperty:
    """Cover line 38: name property."""

    def test_name_returns_init_reserve(self) -> None:
        from axm_init.tools.reserve import InitReserveTool

        tool = InitReserveTool()
        assert tool.name == "init_reserve"
