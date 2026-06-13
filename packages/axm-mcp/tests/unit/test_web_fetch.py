"""Tests for the web_fetch tool — all network calls mocked."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from axm_mcp.web_fetch import _MAX_TEXT_CHARS, WebFetchTool, fetch_page

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


# ── WebFetchTool AXMTool wrapper ──────────────────────────────────────


class TestWebFetchTool:
    """The sync AXMTool wrapper bridges to the async ``fetch_page``."""

    def test_name_is_web_fetch(self) -> None:
        """The tool registers under the ``web_fetch`` MCP name."""
        assert WebFetchTool().name == "web_fetch"

    def test_execute_maps_success_payload_to_toolresult(self) -> None:
        """A successful fetch becomes a ToolResult(success=True) carrying data."""
        payload = {
            "success": True,
            "url": "https://example.com",
            "title": "Hi",
            "text": "body",
            "status_code": 200,
            "mode": "basic",
        }
        with patch(
            "axm_mcp.web_fetch.fetch_page",
            new=AsyncMock(return_value=payload),
        ) as mock_fetch:
            result = WebFetchTool().execute(url="https://example.com", mode="basic")

        mock_fetch.assert_awaited_once_with(url="https://example.com", mode="basic")
        assert result.success is True
        assert result.error is None
        assert result.data["title"] == "Hi"
        assert result.data["status_code"] == 200
        assert "success" not in result.data

    def test_execute_maps_error_payload_to_toolresult(self) -> None:
        """A failed fetch becomes a ToolResult(success=False) carrying the error."""
        payload = {"success": False, "error": "boom", "url": "https://x"}
        with patch(
            "axm_mcp.web_fetch.fetch_page",
            new=AsyncMock(return_value=payload),
        ):
            result = WebFetchTool().execute(url="https://x")

        assert result.success is False
        assert result.error == "boom"
        assert result.data["url"] == "https://x"

    def test_execute_tolerates_none_status_in_data(self) -> None:
        """AC3: a None status_code flows through to ToolResult.data unchanged."""
        payload = {
            "success": True,
            "url": "https://example.com",
            "title": "Hi",
            "text": "body",
            "status_code": None,
            "mode": "basic",
        }
        with patch(
            "axm_mcp.web_fetch.fetch_page",
            new=AsyncMock(return_value=payload),
        ):
            result = WebFetchTool().execute(url="https://example.com")

        assert result.success is True
        assert result.data["status_code"] is None


# ── status default (AC3) ─────────────────────────────────────────────


@patch("axm_mcp.web_fetch._HAS_SCRAPLING", True)
class TestStatusDefault:
    """``status`` is ``None`` (not ``200``) when the page lacks the attribute."""

    @pytest.mark.asyncio
    @patch("axm_mcp.web_fetch.Fetcher")
    async def test_status_defaults_to_none_when_absent(
        self, mock_fetcher_cls: MagicMock
    ) -> None:
        """AC3: status is None — not 200 — when the page has no ``status``."""
        page = MagicMock(spec=["css", "get_all_text"])
        page.css.return_value.get.return_value = "Test Page"
        page.get_all_text.return_value = "Hello world"
        mock_fetcher_cls.get.return_value = page

        result = await fetch_page(url="https://example.com", mode="basic")

        assert result["success"] is True
        assert result["status_code"] is None


# ── docstring honesty (AC2) ──────────────────────────────────────────


def test_fetch_page_docstring_matches_behavior() -> None:
    """AC2: docstring documents auto==basic with no escalation yet."""
    doc = (fetch_page.__doc__ or "").lower()
    assert "no escalation" in doc
    assert "basic" in doc


# ── execute() across event-loop contexts (Fetcher mocked) ────────────


def _make_loop_mock_page() -> MagicMock:
    page = MagicMock(spec=["css", "get_all_text", "status"])
    page.css.return_value.get.return_value = "Title"
    page.get_all_text.return_value = "page body"
    page.status = 200
    return page


@pytest.mark.asyncio
async def test_execute_inside_running_loop() -> None:
    """AC1: execute() does not raise RuntimeError inside a running loop.

    The pytest event loop is already running when this coroutine executes,
    so a naive ``asyncio.run`` inside ``execute`` would raise
    ``RuntimeError: asyncio.run() cannot be called from a running event
    loop``. The hardened wrapper must offload to a thread instead.
    """
    with (
        patch("axm_mcp.web_fetch._HAS_SCRAPLING", True),
        patch("axm_mcp.web_fetch.Fetcher") as mock_fetcher_cls,
    ):
        mock_fetcher_cls.get.return_value = _make_loop_mock_page()

        # We are inside a running loop here (pytest-asyncio).
        assert asyncio.get_running_loop() is not None
        result = WebFetchTool().execute(url="https://example.com", mode="basic")

    assert result.success is True
    assert result.data["title"] == "Title"


def test_execute_outside_loop_still_works() -> None:
    """AC1: execute() still works via the no-loop (asyncio.run) path."""

    async def _fake(**_: Any) -> dict[str, Any]:
        return {"success": True, "title": "Hi", "status_code": None, "mode": "basic"}

    with patch("axm_mcp.web_fetch.fetch_page", new=_fake):
        result = WebFetchTool().execute(url="https://example.com")

    assert result.success is True
    assert result.data["title"] == "Hi"
