"""LRU cache for parsed PackageInfo objects.

Avoids redundant ``analyze_package`` calls when multiple tools
query the same codebase within a single session.

The cache automatically invalidates entries when the set of ``.py``
files in the package directory changes — including **content
modifications** (tracked via mtime).

Example::

    >>> from axm_ast.core.cache import get_package, clear_cache
    >>> pkg = get_package(Path("src/mylib"))  # parses on first call
    >>> pkg2 = get_package(Path("src/mylib"))  # cache hit
    >>> pkg is pkg2
    True
    >>> clear_cache()  # reset for re-parsing
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from axm_ast.core.analyzer import (
    analyze_package,
    fingerprint_source_tree,
    module_dotted_name,
)
from axm_ast.models.nodes import PackageInfo

if TYPE_CHECKING:
    from axm_ast.models.calls import CallSite

logger = logging.getLogger(__name__)

__all__ = [
    "PackageCache",
    "clear_cache",
    "get_call_index",
    "get_calls",
    "get_package",
]

# Type alias for the fingerprint: (path, mtime_ns) pairs.
type _Fingerprint = frozenset[tuple[str, int]]


def _file_fingerprint(path: Path) -> _Fingerprint:
    """Return ``.py`` file paths with mtime for content-change detection.

    Tracks both additions/deletions **and** content modifications by
    including ``st_mtime_ns`` (nanosecond precision) for each file. Delegates
    to :func:`fingerprint_source_tree`, which prunes non-source directories
    (``.venv``/``.git``/``__pycache__``/…) instead of walking the whole tree.
    """
    return fingerprint_source_tree(path)


class PackageCache:
    """Thread-safe cache for ``PackageInfo`` and call-site data.

    Stores results keyed by resolved absolute path.  On cache hit,
    the current ``.py`` file fingerprint (paths + mtime) is compared
    to the fingerprint recorded at parse time — if it differs the
    entry is evicted and the package is re-parsed.
    """

    def __init__(self) -> None:
        self._store: dict[Path, tuple[PackageInfo, _Fingerprint]] = {}
        self._calls_store: dict[Path, dict[str, list[CallSite]]] = {}
        self._index_store: dict[Path, dict[str, list[CallSite]]] = {}
        self._lock = threading.Lock()

    def get(self, path: Path) -> PackageInfo:
        """Return cached ``PackageInfo`` or parse and cache on miss.

        On cache hit the file fingerprint is re-checked; if the set
        of ``.py`` files changed (addition, deletion, **or content
        modification**) the stale entry is evicted and the package
        is re-parsed.

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
                cached_pkg, cached_fp = self._store[key]
                current_fp = _file_fingerprint(key)
                if current_fp == cached_fp:
                    return cached_pkg
                # Stale — evict package, call-sites and index together
                del self._store[key]
                self._calls_store.pop(key, None)
                self._index_store.pop(key, None)

        # Parse outside the lock to avoid blocking other threads
        pkg = analyze_package(key)
        fp = _file_fingerprint(key)
        with self._lock:
            # Double-check: another thread may have populated it
            if key not in self._store:
                self._store[key] = (pkg, fp)
            return self._store[key][0]

    def get_calls(self, path: Path) -> dict[str, list[CallSite]]:
        """Return cached call-sites per module, extracting on first call.

        Call-sites share the same invalidation lifecycle as
        ``PackageInfo`` — when the fingerprint changes, both are
        evicted.

        Args:
            path: Path to the package root directory.

        Returns:
            Dict mapping dotted module names to their call-sites.
        """
        from axm_ast.core.callers import extract_calls

        key = path.resolve()
        # Ensure PackageInfo is cached (also handles fingerprint check)
        pkg = self.get(path)

        with self._lock:
            if key in self._calls_store:
                return self._calls_store[key]

        # Extract outside the lock
        calls_by_module: dict[str, list[CallSite]] = {}
        for mod in pkg.modules:
            mod_name = module_dotted_name(mod.path, pkg.root)
            calls_by_module[mod_name] = extract_calls(mod, module_name=mod_name)

        with self._lock:
            if key not in self._calls_store:
                self._calls_store[key] = calls_by_module
            return self._calls_store[key]

    def get_call_index(self, path: Path) -> dict[str, list[CallSite]]:
        """Return a cached ``symbol -> call-sites`` index for the package.

        Built once from :meth:`get_calls` and reused, turning a
        ``find_callers`` query into an O(1) dict lookup instead of an
        O(total-call-sites) linear scan. Shares the call-site invalidation
        lifecycle (evicted when the fingerprint changes).

        Insertion order matches ``get_calls`` iteration order (module order,
        then in-module call order), so each symbol's list is identical to the
        order a linear scan would have produced.

        Args:
            path: Path to the package root directory.

        Returns:
            Dict mapping symbol name to its call-sites.
        """
        key = path.resolve()
        calls_by_module = self.get_calls(path)

        with self._lock:
            if key in self._index_store:
                return self._index_store[key]

        index: dict[str, list[CallSite]] = {}
        for mod_calls in calls_by_module.values():
            for call in mod_calls:
                index.setdefault(call.symbol, []).append(call)

        with self._lock:
            if key not in self._index_store:
                self._index_store[key] = index
            return self._index_store[key]

    def clear(self) -> None:
        """Invalidate all cached entries."""
        from axm_ast.core.parser import clear_parse_cache

        with self._lock:
            self._store.clear()
            self._calls_store.clear()
            self._index_store.clear()
        clear_parse_cache()


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


def get_calls(path: Path) -> dict[str, list[CallSite]]:
    """Return cached call-sites for *path*, using the global cache.

    Equivalent to extracting calls from every module but avoids
    re-reading files when the package is already cached.

    Args:
        path: Path to the package root directory.

    Returns:
        Dict mapping dotted module names to call-site lists.
    """
    return _cache.get_calls(path)


def get_call_index(path: Path) -> dict[str, list[CallSite]]:
    """Return the cached ``symbol -> call-sites`` index, using the global cache.

    Args:
        path: Path to the package root directory.

    Returns:
        Dict mapping symbol name to its call-sites.
    """
    return _cache.get_call_index(path)


def clear_cache() -> None:
    """Reset the global ``PackageCache``, forcing re-parsing on next call."""
    _cache.clear()
