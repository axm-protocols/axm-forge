"""Web fetch tool — anti-bot web page fetching via Scrapling.

Provides three fetching modes:
- ``basic``: Fast HTTP requests with TLS fingerprinting.
- ``dynamic``: Full browser automation via Playwright/Chromium.
- ``stealth``: Anti-bot bypass with modified Firefox (Camoufox).

Scrapling is an optional dependency. If not installed, the tool
returns a clear error message.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor

from axm.tools.base import ToolResult

__all__ = ["WebFetchTool", "fetch_page"]

FetchResult = dict[str, bool | int | str | None]

logger = logging.getLogger(__name__)

# Lazy-loaded at module level for mockability in tests.
try:
    from scrapling.fetchers import (
        DynamicFetcher,
        Fetcher,
        StealthyFetcher,
    )

    _HAS_SCRAPLING = True
except ImportError:
    Fetcher = None
    DynamicFetcher = None
    StealthyFetcher = None
    _HAS_SCRAPLING = False


_MAX_TEXT_CHARS = 50_000


async def fetch_page(
    *,
    url: str,
    mode: str = "auto",
) -> FetchResult:
    """Fetch a web page with optional anti-bot bypass.

    Uses Scrapling as backend.

    Args:
        url: URL to fetch (required).
        mode: Fetching mode — ``auto``, ``basic``, ``dynamic``,
            or ``stealth``. ``auto`` currently behaves exactly like
            ``basic`` (no escalation yet): there is no automatic
            escalation from ``basic`` to ``dynamic``/``stealth``.

    Returns:
        Dict with ``success``, ``url``, ``title``, ``text``,
        and ``status_code`` on success (``status_code`` is ``None``
        when the backend does not expose a status).
        Dict with ``success=False`` and ``error`` on failure.
    """
    if not _HAS_SCRAPLING:
        logger.error(
            "scrapling is not installed — install with: "
            "pip install 'scrapling[fetchers]'",
        )
        return {
            "success": False,
            "error": (
                "scrapling is not installed. "
                "Install with: pip install 'scrapling[fetchers]'"
            ),
        }

    try:
        match mode:
            case "auto" | "basic":
                page = Fetcher.get(url)
            case "dynamic":
                page = await DynamicFetcher.async_fetch(url)
            case "stealth":
                page = await StealthyFetcher.async_fetch(url)
            case _:
                return {
                    "success": False,
                    "error": (
                        f"Unknown mode: {mode!r}. Use: auto, basic, dynamic, stealth."
                    ),
                }

        title: str = page.css("title::text").get() or ""
        text: str = page.get_all_text() or ""
        if len(text) > _MAX_TEXT_CHARS:
            text = text[:_MAX_TEXT_CHARS] + "\n... [truncated]"
        status: int | None = getattr(page, "status", None)

        return {
            "success": True,
            "url": url,
            "title": title,
            "text": text,
            "status_code": status,
            "mode": mode,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("web_fetch failed for %s: %s", url, exc)
        return {
            "success": False,
            "error": str(exc),
            "url": url,
            "mode": mode,
        }


def _run_sync(coro: Coroutine[object, object, FetchResult]) -> FetchResult:
    """Run an async coroutine to completion from a sync context.

    ``asyncio.run`` raises ``RuntimeError`` when invoked from within an
    already-running event loop. The MCP wrapping layer may call
    :meth:`WebFetchTool.execute` from either context, so detect a running
    loop and offload the coroutine to a dedicated thread (with its own
    loop) when one is active; otherwise use ``asyncio.run`` directly.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class WebFetchTool:
    """AXMTool-compatible wrapper around :func:`fetch_page`.

    The MCP wrapping layer (``register_one``) invokes tools through a
    synchronous ``execute(**kwargs)`` seam, while the central fetching
    logic in :func:`fetch_page` is async. This wrapper bridges the two
    via :func:`asyncio.run` without duplicating any business logic — all
    fetching, mode dispatch, truncation and error handling stay in
    :func:`fetch_page`.
    """

    agent_hint = (
        "Fetch a web page with optional anti-bot bypass "
        "(modes: auto, basic, dynamic, stealth). Returns title, text "
        "and status_code, or a structured error."
    )

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "web_fetch"

    def execute(self, *, url: str, mode: str = "auto", **_: object) -> ToolResult:
        """Fetch a web page, delegating to :func:`fetch_page`.

        Args:
            url: URL to fetch (required).
            mode: Fetching mode — ``auto``, ``basic``, ``dynamic``,
                or ``stealth``. Defaults to ``auto``.
        """
        result = _run_sync(fetch_page(url=url, mode=mode))
        success = bool(result.get("success", False))
        error = result.get("error")
        data = {k: v for k, v in result.items() if k not in {"success", "error"}}
        return ToolResult(
            success=success,
            data=data,
            error=str(error) if error is not None else None,
        )
