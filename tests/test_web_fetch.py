"""Tests for the web_fetch tool — all network calls mocked."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from axm_mcp.web_fetch import _MAX_TEXT_CHARS, fetch_page

# ── Helpers ──────────────────────────────────────────────────────────


def _make_mock_page(title: str = "Test Page", text: str = "Hello world") -> MagicMock:
    """Build a mock Scrapling page object."""
    page = MagicMock()
    page.css.return_value.get.return_value = title
    page.get_all_text.return_value = text
    page.status = 200
    return page


# ── Mode dispatch ────────────────────────────────────────────────────


@patch("axm_mcp.web_fetch._HAS_SCRAPLING", True)
class TestModeDispatch:
    """Verify each mode dispatches to the correct Scrapling fetcher."""

    @pytest.mark.asyncio
    @patch("axm_mcp.web_fetch.Fetcher")
    async def test_basic_mode(self, mock_fetcher_cls: MagicMock) -> None:
        mock_fetcher_cls.get.return_value = _make_mock_page()

        result = await fetch_page(url="https://example.com", mode="basic")

        mock_fetcher_cls.get.assert_called_once_with("https://example.com")
        assert result["success"] is True
        assert result["title"] == "Test Page"
        assert result["text"] == "Hello world"
        assert result["status_code"] == 200

    @pytest.mark.asyncio
    @patch("axm_mcp.web_fetch.Fetcher")
    async def test_auto_defaults_to_basic(self, mock_fetcher_cls: MagicMock) -> None:
        mock_fetcher_cls.get.return_value = _make_mock_page()

        result = await fetch_page(url="https://example.com", mode="auto")

        mock_fetcher_cls.get.assert_called_once_with("https://example.com")
        assert result["success"] is True

    @pytest.mark.asyncio
    @patch("axm_mcp.web_fetch.DynamicFetcher")
    async def test_dynamic_mode(self, mock_dynamic_cls: MagicMock) -> None:
        mock_dynamic_cls.async_fetch = AsyncMock(
            return_value=_make_mock_page(),
        )

        result = await fetch_page(url="https://spa.example.com", mode="dynamic")

        mock_dynamic_cls.async_fetch.assert_awaited_once_with(
            "https://spa.example.com",
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    @patch("axm_mcp.web_fetch.StealthyFetcher")
    async def test_stealth_mode(self, mock_stealth_cls: MagicMock) -> None:
        mock_stealth_cls.async_fetch = AsyncMock(
            return_value=_make_mock_page(),
        )

        result = await fetch_page(url="https://protected.example.com", mode="stealth")

        mock_stealth_cls.async_fetch.assert_awaited_once_with(
            "https://protected.example.com",
        )
        assert result["success"] is True


# ── Error handling ───────────────────────────────────────────────────


@patch("axm_mcp.web_fetch._HAS_SCRAPLING", True)
class TestErrorHandling:
    """Verify graceful error handling for various failure scenarios."""

    @pytest.mark.asyncio
    async def test_unknown_mode_returns_error(self) -> None:
        result = await fetch_page(url="https://example.com", mode="turbo")

        assert result["success"] is False
        assert "Unknown mode" in result["error"]

    @pytest.mark.asyncio
    @patch("axm_mcp.web_fetch.Fetcher")
    async def test_network_error_returns_failure(
        self, mock_fetcher_cls: MagicMock
    ) -> None:
        mock_fetcher_cls.get.side_effect = ConnectionError("DNS resolution failed")

        result = await fetch_page(url="https://down.example.com", mode="basic")

        assert result["success"] is False
        assert "DNS resolution failed" in result["error"]
        assert result["url"] == "https://down.example.com"


# ── Missing dependency ───────────────────────────────────────────────


@patch("axm_mcp.web_fetch._HAS_SCRAPLING", False)
@pytest.mark.asyncio
async def test_scrapling_not_installed() -> None:
    """Verify graceful error when scrapling is not installed."""
    result = await fetch_page(url="https://example.com")

    assert result["success"] is False
    assert "not installed" in result["error"]


# ── Truncation ───────────────────────────────────────────────────────


@patch("axm_mcp.web_fetch._HAS_SCRAPLING", True)
class TestTruncation:
    """Verify text is truncated when exceeding _MAX_TEXT_CHARS."""

    @pytest.mark.asyncio
    @patch("axm_mcp.web_fetch.Fetcher")
    async def test_long_text_is_truncated(self, mock_fetcher_cls: MagicMock) -> None:
        long_text = "x" * (_MAX_TEXT_CHARS + 1000)
        mock_fetcher_cls.get.return_value = _make_mock_page(text=long_text)

        result = await fetch_page(url="https://example.com", mode="basic")

        assert result["success"] is True
        assert len(result["text"]) < len(long_text)
        assert result["text"].endswith("... [truncated]")

    @pytest.mark.asyncio
    @patch("axm_mcp.web_fetch.Fetcher")
    async def test_short_text_not_truncated(self, mock_fetcher_cls: MagicMock) -> None:
        mock_fetcher_cls.get.return_value = _make_mock_page(text="short")

        result = await fetch_page(url="https://example.com", mode="basic")

        assert result["success"] is True
        assert result["text"] == "short"
