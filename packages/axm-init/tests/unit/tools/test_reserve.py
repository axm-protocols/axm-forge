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


class TestReserveDryRunTypeGuard:
    """A non-bool ``dry_run`` is a hard failure, never a silent ``False``.

    Coercing ``dry_run="true"`` to ``False`` would turn a requested dry-run
    into a real PyPI publish — the most dangerous failure direction.
    """

    def test_string_dry_run_rejected(self) -> None:
        from axm_init.tools.reserve import InitReserveTool

        result = InitReserveTool().execute(
            name="some-pkg",
            author="Real Author",
            email="real@example.com",
            dry_run="true",
        )
        assert result.success is False
        assert "dry_run" in (result.error or "")


class TestReserveNameProperty:
    """Cover line 38: name property."""

    def test_name_returns_init_reserve(self) -> None:
        from axm_init.tools.reserve import InitReserveTool

        tool = InitReserveTool()
        assert tool.name == "init_reserve"


class TestReserveTextRendering:
    """Compact text rendering for the LLM-facing ToolResult."""

    @patch("axm_init.core.reserver.reserve_pypi")
    @patch("axm_init.adapters.credentials.CredentialManager")
    def test_dry_run_carries_name_version_and_message(
        self, mock_creds: MagicMock, mock_reserve: MagicMock
    ) -> None:
        """Dry-run reserve surfaces name, version and message in result.text.

        Drives the public boundary: a mocked ``reserve_pypi`` returns a
        dry-run ReserveResult and the rendered ``result.text`` must carry the
        exact ``init_reserve | ✓ | my-pkg | v0.0.1 | <message>`` line.
        """
        from axm_init.models.results import ReserveResult
        from axm_init.tools.reserve import InitReserveTool

        mock_creds.return_value.get_pypi_token.return_value = "tok"
        mock_reserve.return_value = ReserveResult(
            success=True,
            package_name="my-pkg",
            version="0.0.1",
            message="Dry run — would reserve 'my-pkg' on PyPI",
        )
        result = InitReserveTool().execute(
            name="my-pkg",
            author="Real Author",
            email="real@email.com",
            dry_run=True,
        )
        assert result.text == (
            "init_reserve | ✓ | my-pkg | v0.0.1 | "
            "Dry run — would reserve 'my-pkg' on PyPI"
        )

    @patch("axm_init.core.reserver.reserve_pypi")
    @patch("axm_init.adapters.credentials.CredentialManager")
    def test_success_populates_text(
        self, mock_creds: MagicMock, mock_reserve: MagicMock
    ) -> None:
        from axm_init.models.results import ReserveResult
        from axm_init.tools.reserve import InitReserveTool

        mock_creds.return_value.get_pypi_token.return_value = "tok"
        mock_reserve.return_value = ReserveResult(
            success=True,
            package_name="test-pkg",
            version="0.0.1",
            message="Reserved 'test-pkg' on PyPI",
        )
        result = InitReserveTool().execute(
            name="test-pkg", author="Real Author", email="real@email.com"
        )
        assert result.text == (
            "init_reserve | ✓ | test-pkg | v0.0.1 | Reserved 'test-pkg' on PyPI"
        )
        assert result.data is not None
        assert result.data["package_name"] == "test-pkg"

    @patch("axm_init.core.reserver.reserve_pypi")
    @patch("axm_init.adapters.credentials.CredentialManager")
    def test_failure_leaves_text_none(
        self, mock_creds: MagicMock, mock_reserve: MagicMock
    ) -> None:
        from axm_init.models.results import ReserveResult
        from axm_init.tools.reserve import InitReserveTool

        mock_creds.return_value.get_pypi_token.return_value = "tok"
        mock_reserve.return_value = ReserveResult(
            success=False,
            package_name="taken-pkg",
            version="0.0.1",
            message="Package 'taken-pkg' is already taken on PyPI",
        )
        result = InitReserveTool().execute(
            name="taken-pkg", author="Real Author", email="real@email.com"
        )
        assert result.text is None
        assert result.success is False
