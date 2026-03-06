"""Tests for the web_fetch tool — all network calls mocked."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from axm_mcp.web_fetch import fetch_page

# ── Helpers ──────────────────────────────────────────────────────────


def _make_mock_page(title: str = "Test Page", text: str = "Hello world") -> MagicMock:
    """Build a mock Scrapling page object."""
    page = MagicMock()
    page.css.return_value.get.return_value = title
    page.get_text.return_value = text
    page.status = 200
    return page


# ── Mode dispatch ────────────────────────────────────────────────────


@patch("axm_mcp.web_fetch._HAS_SCRAPLING", True)
class TestModeDispatch:
    """Verify each mode dispatches to the correct Scrapling fetcher."""

    @patch("axm_mcp.web_fetch.Fetcher")
    def test_basic_mode(self, mock_fetcher_cls: MagicMock) -> None:
        mock_fetcher_cls.get.return_value = _make_mock_page()

        result = fetch_page(url="https://example.com", mode="basic")

        mock_fetcher_cls.get.assert_called_once_with("https://example.com")
        assert result["success"] is True
        assert result["title"] == "Test Page"
        assert result["text"] == "Hello world"
        assert result["status_code"] == 200

    @patch("axm_mcp.web_fetch.Fetcher")
    def test_auto_defaults_to_basic(self, mock_fetcher_cls: MagicMock) -> None:
        mock_fetcher_cls.get.return_value = _make_mock_page()

        result = fetch_page(url="https://example.com", mode="auto")

        mock_fetcher_cls.get.assert_called_once_with("https://example.com")
        assert result["success"] is True

    @patch("axm_mcp.web_fetch.DynamicFetcher")
    def test_dynamic_mode(self, mock_dynamic_cls: MagicMock) -> None:
        mock_dynamic_cls.fetch.return_value = _make_mock_page()

        result = fetch_page(url="https://spa.example.com", mode="dynamic")

        mock_dynamic_cls.fetch.assert_called_once_with("https://spa.example.com")
        assert result["success"] is True

    @patch("axm_mcp.web_fetch.StealthyFetcher")
    def test_stealth_mode(self, mock_stealth_cls: MagicMock) -> None:
        mock_stealth_cls.fetch.return_value = _make_mock_page()

        result = fetch_page(url="https://protected.example.com", mode="stealth")

        mock_stealth_cls.fetch.assert_called_once_with("https://protected.example.com")
        assert result["success"] is True


# ── Error handling ───────────────────────────────────────────────────


@patch("axm_mcp.web_fetch._HAS_SCRAPLING", True)
class TestErrorHandling:
    """Verify graceful error handling for various failure scenarios."""

    def test_unknown_mode_returns_error(self) -> None:
        result = fetch_page(url="https://example.com", mode="turbo")

        assert result["success"] is False
        assert "Unknown mode" in result["error"]

    @patch("axm_mcp.web_fetch.Fetcher")
    def test_network_error_returns_failure(self, mock_fetcher_cls: MagicMock) -> None:
        mock_fetcher_cls.get.side_effect = ConnectionError("DNS resolution failed")

        result = fetch_page(url="https://down.example.com", mode="basic")

        assert result["success"] is False
        assert "DNS resolution failed" in result["error"]
        assert result["url"] == "https://down.example.com"


# ── Missing dependency ───────────────────────────────────────────────


@patch("axm_mcp.web_fetch._HAS_SCRAPLING", False)
def test_scrapling_not_installed() -> None:
    """Verify graceful error when scrapling is not installed."""
    result = fetch_page(url="https://example.com")

    assert result["success"] is False
    assert "not installed" in result["error"]
