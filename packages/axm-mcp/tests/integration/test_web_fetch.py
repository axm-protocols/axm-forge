"""Integration tests for WebFetchTool.execute under a running event loop."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from axm_mcp.web_fetch import WebFetchTool


def _make_mock_page() -> MagicMock:
    page = MagicMock(spec=["css", "get_all_text", "status"])
    page.css.return_value.get.return_value = "Title"
    page.get_all_text.return_value = "page body"
    page.status = 200
    return page


@pytest.mark.integration
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
        mock_fetcher_cls.get.return_value = _make_mock_page()

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
