"""LRU cache for parsed PackageInfo objects.

Avoids redundant ``analyze_package`` calls when multiple tools
query the same codebase within a single session.

Example::

    >>> from axm_ast.core.cache import get_package, clear_cache
    >>> pkg = get_package(Path("src/mylib"))  # parses on first call
    >>> pkg2 = get_package(Path("src/mylib"))  # cache hit
    >>> pkg is pkg2
    True
    >>> clear_cache()  # reset for re-parsing
"""

from __future__ import annotations

import threading
from pathlib import Path

from axm_ast.core.analyzer import analyze_package
from axm_ast.models.nodes import PackageInfo

__all__ = ["PackageCache", "clear_cache", "get_package"]


class PackageCache:
    """Thread-safe cache for ``PackageInfo`` objects.

    Stores results keyed by resolved absolute path. No TTL — designed
    for short-lived MCP sessions where manual invalidation via
    ``clear()`` is sufficient.
    """

    def __init__(self) -> None:
        self._store: dict[Path, PackageInfo] = {}
        self._lock = threading.Lock()

    def get(self, path: Path) -> PackageInfo:
        """Return cached ``PackageInfo`` or parse and cache on miss.

        Args:
            path: Path to the package root directory.

        Returns:
            Cached or freshly parsed ``PackageInfo``.

        Raises:
            ValueError: If path is not a directory (from ``analyze_package``).
        """
        key = path.resolve()
        with self._lock:
            if key in self._store:
                return self._store[key]
        # Parse outside the lock to avoid blocking other threads
        pkg = analyze_package(key)
        with self._lock:
            # Double-check: another thread may have populated it
            if key not in self._store:
                self._store[key] = pkg
            return self._store[key]

    def clear(self) -> None:
        """Invalidate all cached entries."""
        with self._lock:
            self._store.clear()


# ─── Module-level singleton ──────────────────────────────────────────────────

_cache = PackageCache()


def get_package(path: Path) -> PackageInfo:
    """Return ``PackageInfo`` for *path*, using the global cache.

    Equivalent to ``analyze_package(path)`` but avoids re-parsing
    if the same *path* was already analyzed in this session.

    Args:
        path: Path to the package root directory.

    Returns:
        Cached or freshly parsed ``PackageInfo``.
    """
    return _cache.get(path)


def clear_cache() -> None:
    """Reset the global ``PackageCache``, forcing re-parsing on next call."""
    _cache.clear()
