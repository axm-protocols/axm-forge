"""Tests for tools.reserve — test mirror."""

from __future__ import annotations

from unittest.mock import ANY, MagicMock, patch

import pytest


class TestReserveToolValidation:
    """Validate required kwargs handling."""

    def test_missing_name_returns_error(self) -> None:
        """Calling execute() without 'name' returns a ToolResult error."""
        from axm_init.tools.reserve import InitReserveTool

        tool = InitReserveTool()
        result = tool.execute()
        assert result.success is False
        assert "'name' is required" in (result.error or "")

    @pytest.mark.parametrize(
        ("author", "email", "expected_substring"),
        [
            pytest.param("", "a@b.com", "author", id="empty_author"),
            pytest.param(
                "John Doe", "real@email.com", "placeholder", id="placeholder_author"
            ),
            pytest.param("Real Author", "", "email", id="empty_email"),
            pytest.param(
                "Real Author",
                "john.doe@example.com",
                "placeholder",
                id="placeholder_email",
            ),
        ],
    )
    def test_tool_rejects_invalid_identity(
        self, author: str, email: str, expected_substring: str
    ) -> None:
        """Invalid author/email values return ToolResult error."""
        from axm_init.tools.reserve import InitReserveTool

        tool = InitReserveTool()
        result = tool.execute(name="test-pkg", author=author, email=email)
        assert result.success is False
        assert expected_substring in (result.error or "").lower()

    @pytest.mark.parametrize(
        ("reserve_success", "reserve_version", "reserve_message"),
        [
            pytest.param(True, "0.1.0", "Reserved test-package", id="success"),
            pytest.param(False, "", "Package name taken", id="failure"),
        ],
    )
    @patch("axm_init.core.reserver.reserve_pypi")
    @patch("axm_init.adapters.credentials.CredentialManager")
    def test_reserve_propagates_result_success(
        self,
        mock_creds: MagicMock,
        mock_reserve: MagicMock,
        reserve_success: bool,
        reserve_version: str,
        reserve_message: str,
    ) -> None:
        """InitReserveTool propagates underlying reserve_pypi success flag."""
        from axm_init.models.results import ReserveResult
        from axm_init.tools.reserve import InitReserveTool

        mock_creds.return_value.get_pypi_token.return_value = "fake-token"
        mock_reserve.return_value = ReserveResult(
            success=reserve_success,
            package_name="test-package",
            version=reserve_version,
            message=reserve_message,
        )
        tool = InitReserveTool()
        result = tool.execute(
            name="test-package", author="Author", email="email@test.com"
        )
        assert result.success is reserve_success

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

    @pytest.mark.parametrize(
        ("stored_token", "expected_token_arg"),
        [
            pytest.param(None, "", id="no_token_uses_empty"),
            pytest.param("real-token", "real-token", id="with_token_passes_through"),
        ],
    )
    @patch("axm_init.core.reserver.reserve_pypi")
    @patch("axm_init.adapters.credentials.CredentialManager")
    def test_dry_run_token_handling(
        self,
        mock_creds: MagicMock,
        mock_reserve: MagicMock,
        stored_token: str | None,
        expected_token_arg: str,
    ) -> None:
        """dry_run=True forwards stored token (or '' if absent) to reserve_pypi."""
        from axm_init.models.results import ReserveResult
        from axm_init.tools.reserve import InitReserveTool

        mock_creds.return_value.get_pypi_token.return_value = stored_token
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
            token=expected_token_arg,
            dry_run=True,
            checker=ANY,
        )


class TestReserveNameProperty:
    """Cover line 38: name property."""

    def test_name_returns_init_reserve(self) -> None:
        from axm_init.tools.reserve import InitReserveTool

        tool = InitReserveTool()
        assert tool.name == "init_reserve"
