"""Bounded cache for parsed PackageInfo objects.

Avoids redundant ``analyze_package`` calls when multiple tools
query the same codebase within a single session.

The cache automatically invalidates entries when the set of ``.py``
files in the package directory changes — including **content
modifications** (tracked via mtime).

The cache is pure memoization: correctness comes from the fingerprint
check on every hit, so an evicted entry simply behaves like a cache miss
(the package is re-parsed). To keep a long-lived process (the shared MCP
daemon) from growing without limit, entries are also evicted when:

* **dead path** — the key directory no longer exists (e.g. a deleted
  temporary git worktree);
* **idle TTL** — the entry was not accessed for ``ttl_seconds``
  (env ``AXM_AST_CACHE_TTL_S``, default 1800 s, ``0`` disables);
* **weight ceiling** — the total *estimated* weight exceeds
  ``max_weight_bytes`` (env ``AXM_AST_CACHE_MAX_MB``, default 1024 MiB,
  ``0`` disables): least recently used entries go first, but the entry
  being inserted or returned is never evicted.

Dead paths and idle entries are dropped by an opportunistic sweep,
throttled to once per ``sweep_interval_seconds`` (default 60 s).

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
import math
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from axm_ast.core.analyzer import (
    analyze_package,
    fingerprint_source_tree,
    module_dotted_name,
)
from axm_ast.models.nodes import PackageInfo

if TYPE_CHECKING:
    from collections.abc import Callable

    from axm_ast.models.calls import CallSite

logger = logging.getLogger(__name__)

__all__ = [
    "CacheLimits",
    "CacheStats",
    "PackageCache",
    "cache_stats",
    "clear_cache",
    "get_call_index",
    "get_calls",
    "get_package",
]

# Type alias for the fingerprint: (path, mtime_ns) pairs.
type _Fingerprint = frozenset[tuple[str, int]]

type _EvictReason = Literal["stale", "dead", "ttl", "weight"]
_EVICT_REASONS: tuple[_EvictReason, ...] = ("stale", "dead", "ttl", "weight")

_KIB = 1024
_MIB = 1024 * _KIB

# ─── Defaults & configuration ────────────────────────────────────────────────

_MAX_WEIGHT_ENV = "AXM_AST_CACHE_MAX_MB"
_TTL_ENV = "AXM_AST_CACHE_TTL_S"
_DEFAULT_MAX_WEIGHT_MB = 1024.0
_DEFAULT_TTL_SECONDS = 1800.0
_DEFAULT_SWEEP_INTERVAL_SECONDS = 60.0

# ─── Weight proxy ────────────────────────────────────────────────────────────
# Cheap deterministic estimate of an entry's retained bytes, computed from
# counts already in hand (no deep ``sys.getsizeof`` walk). Calibrated with
# ``tracemalloc`` on the axm-forge packages (2026-10-21): ``PackageInfo``
# retains ~2.2 KiB per symbol (functions, methods, classes, imports and
# variables; per-module overhead included), call-sites ~1.24 KiB each and the
# symbol index ~32 B per call-site reference. The proxy over-estimates
# slightly (axm-audit: ~14 MiB estimated vs 13.1 MiB traced); the median
# entry measured in the shared MCP daemon is ~5 MiB (p90 13 MiB, max 26 MiB).
# Process footprint runs ~1.4-1.7x the traced bytes (allocator overhead).
_ENTRY_BASE_BYTES = 16 * _KIB
_BYTES_PER_FINGERPRINT_FILE = 256
_BYTES_PER_MODULE = 8 * _KIB
_BYTES_PER_SYMBOL = 2 * _KIB
_BYTES_PER_CALL_SITE = 1280
_BYTES_PER_INDEX_REF = 32


def _env_limit(name: str, default: float) -> float | None:
    """Read a numeric cache limit from the environment variable *name*.

    Unset or blank returns *default*; ``0`` returns ``None`` (limit
    disabled). Unparsable, negative or non-finite values fall back to
    *default* with a warning — a typo must never unbound the cache.
    """
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        value = -1.0
    if not math.isfinite(value) or value < 0:
        logger.warning("Ignoring invalid %s=%r; using default %s", name, raw, default)
        return default
    return value if value > 0 else None


@dataclass(frozen=True, slots=True)
class CacheLimits:
    """Memory bounds of a :class:`PackageCache`.

    The defaults are safe without any configuration.

    Attributes:
        max_weight_bytes: Ceiling on the total estimated weight; least
            recently used entries are evicted above it. ``None`` disables.
        ttl_seconds: Idle duration after which the sweep evicts an entry.
            ``None`` disables.
        sweep_interval_seconds: Minimum delay between two opportunistic
            sweeps (dead paths + idle TTL). ``0`` sweeps on every access.
    """

    max_weight_bytes: int | None = int(_DEFAULT_MAX_WEIGHT_MB * _MIB)
    ttl_seconds: float | None = _DEFAULT_TTL_SECONDS
    sweep_interval_seconds: float = _DEFAULT_SWEEP_INTERVAL_SECONDS

    @classmethod
    def from_env(cls) -> CacheLimits:
        """Build limits from ``AXM_AST_CACHE_MAX_MB`` / ``AXM_AST_CACHE_TTL_S``.

        ``AXM_AST_CACHE_MAX_MB`` is a size in MiB of *estimated* weight and
        ``AXM_AST_CACHE_TTL_S`` an idle duration in seconds; ``0`` disables
        the corresponding bound.
        """
        max_mb = _env_limit(_MAX_WEIGHT_ENV, _DEFAULT_MAX_WEIGHT_MB)
        return cls(
            max_weight_bytes=None if max_mb is None else int(max_mb * _MIB),
            ttl_seconds=_env_limit(_TTL_ENV, _DEFAULT_TTL_SECONDS),
        )


@dataclass(frozen=True, slots=True)
class CacheStats:
    """Read-only snapshot of a :class:`PackageCache` for diagnostics.

    Hits and misses count :meth:`PackageCache.get` lookups (a miss is a
    parse). Evictions are split by reason: ``stale`` (fingerprint changed),
    ``dead`` (directory gone), ``ttl`` (idle) and ``weight`` (LRU over the
    ceiling).
    """

    entries: int
    weight_bytes: int
    max_weight_bytes: int | None
    ttl_seconds: float | None
    hits: int
    misses: int
    evicted_stale: int
    evicted_dead: int
    evicted_ttl: int
    evicted_weight: int


@dataclass(slots=True)
class _CacheEntry:
    """One cached package with its derived call data, sharing one lifecycle.

    Call-sites and the symbol index live *inside* the entry, so they are
    evicted together with their package and can never outlive or diverge
    from it.
    """

    package: PackageInfo
    fingerprint: _Fingerprint
    last_access: float
    package_weight: int
    calls: dict[str, list[CallSite]] | None = None
    calls_weight: int = 0
    index: dict[str, list[CallSite]] | None = None
    index_weight: int = 0

    @property
    def weight(self) -> int:
        """Estimated retained bytes of the package and attached call data."""
        weight = self.package_weight
        if self.calls is not None:
            weight += self.calls_weight
        if self.index is not None:
            weight += self.index_weight
        return weight


def _package_weight(pkg: PackageInfo, fingerprint: _Fingerprint) -> int:
    """Estimate the retained bytes of *pkg* (see the weight proxy above)."""
    symbols = 0
    for mod in pkg.modules:
        symbols += len(mod.functions) + len(mod.imports) + len(mod.variables)
        symbols += sum(1 + len(cls.methods) for cls in mod.classes)
    return (
        _ENTRY_BASE_BYTES
        + len(fingerprint) * _BYTES_PER_FINGERPRINT_FILE
        + len(pkg.modules) * _BYTES_PER_MODULE
        + symbols * _BYTES_PER_SYMBOL
    )


def _sites_count(by_name: dict[str, list[CallSite]]) -> int:
    """Total number of call-site references in a ``name -> sites`` mapping."""
    return sum(len(sites) for sites in by_name.values())


def _file_fingerprint(path: Path) -> _Fingerprint:
    """Return ``.py`` file paths with mtime for content-change detection.

    Tracks both additions/deletions **and** content modifications by
    including ``st_mtime_ns`` (nanosecond precision) for each file. Delegates
    to :func:`fingerprint_source_tree`, which prunes non-source directories
    (``.venv``/``.git``/``__pycache__``/…) instead of walking the whole tree.
    """
    return fingerprint_source_tree(path)


class PackageCache:
    """Thread-safe, memory-bounded cache for ``PackageInfo`` and call-sites.

    Stores results keyed by resolved absolute path.  On cache hit,
    the current ``.py`` file fingerprint (paths + mtime) is compared
    to the fingerprint recorded at parse time — if it differs the
    entry is evicted and the package is re-parsed.

    Each key holds a single entry (package, fingerprint, optional
    call-sites and symbol index), kept in LRU order. Entries are also
    evicted when their directory disappears, when idle longer than
    ``limits.ttl_seconds`` or, least recently used first, when the total
    estimated weight exceeds ``limits.max_weight_bytes``. Every eviction
    behaves exactly like a cache miss.

    Args:
        limits: Memory bounds; defaults to :class:`CacheLimits` defaults.
        clock: Monotonic time source in seconds (injectable for tests).
    """

    def __init__(
        self,
        limits: CacheLimits | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limits = limits if limits is not None else CacheLimits()
        self._clock = clock
        self._entries: OrderedDict[Path, _CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions: dict[_EvictReason, int] = dict.fromkeys(_EVICT_REASONS, 0)
        self._last_sweep = clock()

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
            cached = self._lookup(key)
            if cached is not None:
                return cached

        # Capture the fingerprint BEFORE parsing so the stored fingerprint
        # reflects the file state the analysis actually saw. Capturing it after
        # ``analyze_package`` would bake a modification made *during* analysis
        # into the fingerprint, leaving the entry permanently stale (the next
        # ``get`` would see ``current_fp == cached_fp`` and never re-parse).
        fp = _file_fingerprint(key)
        # Parse outside the lock to avoid blocking other threads
        pkg = analyze_package(key)
        weight = _package_weight(pkg, fp)
        with self._lock:
            # Double-check: another thread may have populated it
            entry = self._entries.get(key)
            if entry is None:
                entry = _CacheEntry(pkg, fp, self._clock(), weight)
                self._entries[key] = entry
                self._enforce_weight(protect=key)
            else:
                self._touch(key, entry, self._clock())
            return entry.package

    def get_calls(self, path: Path) -> dict[str, list[CallSite]]:
        """Return cached call-sites per module, extracting on first call.

        Call-sites share the same invalidation lifecycle as
        ``PackageInfo`` — they live in the package's cache entry, so
        any eviction (stale fingerprint, dead path, TTL, weight) drops
        both together.

        Concurrency: best-effort double-checked locking. The store is
        read under the lock, the call-sites are extracted *outside* the
        lock (to avoid blocking other threads), then re-checked under the
        lock before writing. Two concurrent first-callers may both extract,
        but the race is benign: the values are pure functions of the same
        ``PackageInfo``, so they are equivalent, and ``first write wins``
        (the re-check skips the second store). The cost is a wasted
        recompute, never corruption — so no lock is held during extraction.
        If the entry was evicted or replaced meanwhile, the call-sites are
        returned without being stored (exactly like a cache miss).

        Args:
            path: Path to the package root directory.

        Returns:
            Dict mapping dotted module names to their call-sites.
        """
        from axm_ast.core.extract import extract_calls

        key = path.resolve()
        # Ensure PackageInfo is cached (also handles fingerprint check)
        pkg = self.get(path)

        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and entry.package is pkg and entry.calls is not None:
                return entry.calls

        # Extract outside the lock
        calls_by_module: dict[str, list[CallSite]] = {}
        for mod in pkg.modules:
            mod_name = module_dotted_name(mod.path, pkg.root)
            calls_by_module[mod_name] = extract_calls(mod, module_name=mod_name)
        weight = _sites_count(calls_by_module) * _BYTES_PER_CALL_SITE

        with self._lock:
            entry = self._entries.get(key)
            if entry is None or entry.package is not pkg:
                return calls_by_module
            if entry.calls is None:
                entry.calls = calls_by_module
                entry.calls_weight = weight
                self._enforce_weight(protect=key)
            return entry.calls

    def get_call_index(self, path: Path) -> dict[str, list[CallSite]]:
        """Return a cached ``symbol -> call-sites`` index for the package.

        Built once from :meth:`get_calls` and reused, turning a
        ``find_callers`` query into an O(1) dict lookup instead of an
        O(total-call-sites) linear scan. Shares the call-site invalidation
        lifecycle (stored in the same cache entry, evicted with it).

        Insertion order matches ``get_calls`` iteration order (module order,
        then in-module call order), so each symbol's list is identical to the
        order a linear scan would have produced.

        Concurrency: best-effort double-checked locking, same pattern as
        :meth:`get_calls`. The index is built *outside* the lock and the
        store is re-checked under the lock before writing. Two concurrent
        first-callers may both build the index, but the race is benign: the
        index is a pure function of the same call-sites, so the results are
        equivalent, and ``first write wins`` (the re-check skips the second
        store). The cost is a wasted recompute, never corruption.

        Args:
            path: Path to the package root directory.

        Returns:
            Dict mapping symbol name to its call-sites.
        """
        key = path.resolve()
        calls_by_module = self.get_calls(path)

        with self._lock:
            entry = self._entries.get(key)
            if (
                entry is not None
                and entry.calls is calls_by_module
                and entry.index is not None
            ):
                return entry.index

        index: dict[str, list[CallSite]] = {}
        for mod_calls in calls_by_module.values():
            for call in mod_calls:
                index.setdefault(call.symbol, []).append(call)
        weight = _sites_count(index) * _BYTES_PER_INDEX_REF

        with self._lock:
            entry = self._entries.get(key)
            if entry is None or entry.calls is not calls_by_module:
                return index
            if entry.index is None:
                entry.index = index
                entry.index_weight = weight
                self._enforce_weight(protect=key)
            return entry.index

    def clear(self) -> None:
        """Invalidate all cached entries and reset the statistics."""
        from axm_ast.core.parser import clear_parse_cache

        with self._lock:
            self._entries.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = dict.fromkeys(_EVICT_REASONS, 0)
            self._last_sweep = self._clock()
        clear_parse_cache()

    def stats(self) -> CacheStats:
        """Return a read-only snapshot of size, limits and counters."""
        with self._lock:
            return CacheStats(
                entries=len(self._entries),
                weight_bytes=self._total_weight(),
                max_weight_bytes=self._limits.max_weight_bytes,
                ttl_seconds=self._limits.ttl_seconds,
                hits=self._hits,
                misses=self._misses,
                evicted_stale=self._evictions["stale"],
                evicted_dead=self._evictions["dead"],
                evicted_ttl=self._evictions["ttl"],
                evicted_weight=self._evictions["weight"],
            )

    # ── Internals (all called with ``self._lock`` held) ─────────────────────

    def _lookup(self, key: Path) -> PackageInfo | None:
        """Return the still-valid cached package for *key*, else ``None``.

        Runs the throttled sweep first (sparing *key*), then validates the
        entry: a vanished directory is a ``dead`` eviction, a changed
        fingerprint a ``stale`` one. Either way the caller re-parses.
        """
        now = self._clock()
        self._maybe_sweep(now, protect=key)
        entry = self._entries.get(key)
        if entry is not None:
            if not key.is_dir():
                self._evict(key, "dead")
            elif _file_fingerprint(key) == entry.fingerprint:
                self._touch(key, entry, now)
                self._hits += 1
                return entry.package
            else:
                # Stale — evict package, call-sites and index together
                self._evict(key, "stale")
        self._misses += 1
        return None

    def _touch(self, key: Path, entry: _CacheEntry, now: float) -> None:
        """Mark *entry* as most recently used."""
        entry.last_access = now
        self._entries.move_to_end(key)

    def _evict(self, key: Path, reason: _EvictReason) -> None:
        """Drop *key*'s entry (package, call-sites, index) and count why."""
        del self._entries[key]
        self._evictions[reason] += 1
        logger.debug("PackageCache evicted %s (%s)", key, reason)

    def _maybe_sweep(self, now: float, protect: Path) -> None:
        """Evict idle and dead-path entries, at most once per sweep interval.

        Costs one ``is_dir`` stat per entry, never a source-tree walk.
        *protect* (the key being accessed) is left to :meth:`_lookup`.
        """
        if now - self._last_sweep < self._limits.sweep_interval_seconds:
            return
        self._last_sweep = now
        ttl = self._limits.ttl_seconds
        for key, entry in list(self._entries.items()):
            if key == protect:
                continue
            if ttl is not None and now - entry.last_access > ttl:
                self._evict(key, "ttl")
            elif not key.is_dir():
                self._evict(key, "dead")

    def _enforce_weight(self, protect: Path) -> None:
        """Evict least recently used entries until under the weight ceiling.

        *protect* (the entry just inserted or extended) is never evicted, so
        a single package heavier than the ceiling stays cached instead of
        being re-parsed on every call.
        """
        ceiling = self._limits.max_weight_bytes
        if ceiling is None:
            return
        total = self._total_weight()
        for key in list(self._entries):
            if total <= ceiling:
                break
            if key == protect:
                continue
            total -= self._entries[key].weight
            self._evict(key, "weight")

    def _total_weight(self) -> int:
        """Sum of the entries' estimated weights."""
        return sum(entry.weight for entry in self._entries.values())


# ─── Module-level singleton ──────────────────────────────────────────────────

_cache = PackageCache(CacheLimits.from_env())


def get_package(path: Path) -> PackageInfo:
    """Return ``PackageInfo`` for *path*, using the global cache.

    Equivalent to ``analyze_package(path)`` but avoids re-parsing
    if the same *path* was already analyzed in this session.

    Args:
        path: Path to the package root directory.

    Returns:
        Cached or freshly parsed ``PackageInfo``.
    """
    from axm.tools.dependency_reads import current_read_contract

    if current_read_contract() is not None:
        from axm_ast.core.analyzer import analyze_package

        return analyze_package(path)
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


def cache_stats() -> CacheStats:
    """Return a read-only snapshot of the global ``PackageCache``."""
    return _cache.stats()
