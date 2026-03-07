"""Web fetch tool — anti-bot web page fetching via Scrapling.

Provides three fetching modes:
- ``basic``: Fast HTTP requests with TLS fingerprinting.
- ``dynamic``: Full browser automation via Playwright/Chromium.
- ``stealth``: Anti-bot bypass with modified Firefox (Camoufox).

Scrapling is an optional dependency. If not installed, the tool
returns a clear error message.
"""

from __future__ import annotations

import logging
from typing import Any

__all__ = ["fetch_page"]

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
) -> dict[str, Any]:
    """Fetch a web page with optional anti-bot bypass.

    Uses Scrapling as backend with automatic escalation.

    Args:
        url: URL to fetch (required).
        mode: Fetching mode — ``auto``, ``basic``, ``dynamic``,
            or ``stealth``. Defaults to ``auto`` (same as ``basic``).

    Returns:
        Dict with ``success``, ``url``, ``title``, ``text``,
        and ``status_code`` on success.
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
        status: int = getattr(page, "status", 200)

        return {
            "success": True,
            "url": url,
            "title": title,
            "text": text,
            "status_code": status,
            "mode": mode,
        }
    except Exception as exc:
        logger.warning("web_fetch failed for %s: %s", url, exc)
        return {
            "success": False,
            "error": str(exc),
            "url": url,
            "mode": mode,
        }
