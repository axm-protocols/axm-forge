"""Benchmark + equivalence harness for the caller / graph analysis paths.

Measures the cost of the caller-analysis pipeline on axm-ast's *own* source
tree and emits a deterministic fingerprint of the results so the optimized
implementation can be proven byte-for-byte equivalent to the baseline.

Run it against both revisions and compare::

    # optimized (current working tree)
    uv run python benchmarks/bench_callers.py

    # baseline
    git stash && uv run python benchmarks/bench_callers.py ; git stash pop

The "fingerprint" line must be identical across both runs; the "timings"
show the speed-up.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

from axm_ast.core import cache as _cache_mod
from axm_ast.core.analyzer import analyze_package, search_symbols
from axm_ast.core.cache import clear_cache, get_calls, get_package
from axm_ast.core.callers import find_callers
from axm_ast.tools.graph import GraphTool


def _drop_call_sites_only() -> None:
    """Evict cached call-sites but keep PackageInfo and the parse cache.

    Reproduces the in-session state right after ``get_package`` where a tool
    asks "who calls X?" for the first time: the baseline re-reads and
    re-parses every module here; the optimized build serves trees from the
    parse cache.
    """
    _cache_mod._cache._calls_store.clear()

# Default target is a *sibling* package, not axm-ast itself: the benchmark is
# run once on the baseline and once on the optimized tree, and the analyzed
# source must be byte-identical across both for the fingerprint comparison to
# be meaningful. Pass an explicit path as argv[1] to override.
_DEFAULT_TARGET = (
    Path(__file__).resolve().parents[2] / "axm-init" / "src" / "axm_init"
)
PKG = (
    Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else _DEFAULT_TARGET
).resolve()


def _all_symbol_names(pkg: object) -> list[str]:
    """Every distinct function/class name in the package, sorted."""
    names = {sym.name for _mod, sym in search_symbols(pkg)}  # type: ignore[arg-type]
    return sorted(names)


def _callers_fingerprint() -> tuple[str, int]:
    """Stable hash of find_callers() results over every symbol.

    Returns (sha256_hex, total_call_site_count). Independent of timing and
    of caching, so the optimized and baseline builds must produce identical
    values.
    """
    clear_cache()
    pkg = get_package(PKG)
    rows: list[tuple[str, str, int, int, str]] = []
    for name in _all_symbol_names(pkg):
        for c in find_callers(pkg, name):
            rows.append((c.module, c.symbol, c.line, c.column, c.call_expression))
    rows.sort()
    blob = json.dumps(rows, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest(), len(rows)


def _time(label: str, fn: object, repeat: int = 5) -> float:
    """Run *fn* *repeat* times, return best (min) wall-clock seconds."""
    best = float("inf")
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()  # type: ignore[operator]
        best = min(best, time.perf_counter() - t0)
    print(f"  {label:<42} {best * 1000:8.2f} ms  (best of {repeat})")
    return best


def _scenario_cold_callers() -> None:
    """Full caller pipeline from a cold cache: analyze + extract all calls.

    This is the path where the baseline re-parses every file a second time
    (once in analyze_package, once in get_calls).
    """
    clear_cache()
    pkg = get_package(PKG)
    get_calls(PKG)
    # touch a handful of symbols to exercise the lookup
    for name in ("find_callers", "analyze_package", "GraphTool", "parse_file"):
        find_callers(pkg, name)


def _scenario_extract_only() -> None:
    """Just the call-extraction pass over an already-analyzed package.

    Isolates the redundant re-parse: analyze first (warms parse cache),
    then force fresh call extraction.
    """
    clear_cache()
    get_package(PKG)  # analyze pass — parses every file once
    get_calls(PKG)  # baseline re-parses here; optimized hits the parse cache


def _scenario_recompute_calls() -> None:
    """Isolated win: re-extract call-sites with package already analyzed.

    Setup (warm package + parse cache) happens outside the timed region via
    ``_recompute_setup``; here we only drop the call-site cache and rebuild
    it — exactly the redundant second parse the optimization removes.
    """
    _drop_call_sites_only()
    get_calls(PKG)


def _recompute_setup() -> None:
    """Warm PackageInfo + parse cache so _scenario_recompute_calls is isolated."""
    clear_cache()
    get_package(PKG)
    get_calls(PKG)


_QUERY_NAMES: list[str] = []


def _query_setup() -> None:
    """Warm package + call-sites and collect every symbol name to query."""
    clear_cache()
    pkg = get_package(PKG)
    get_calls(PKG)
    _QUERY_NAMES[:] = _all_symbol_names(pkg)
    # One warm-up query so the optimized index is built before timing.
    find_callers(pkg, _QUERY_NAMES[0] if _QUERY_NAMES else "x")


def _scenario_query_all_symbols() -> None:
    """Run find_callers for every symbol — baseline scans all calls per query."""
    pkg = get_package(PKG)
    for name in _QUERY_NAMES:
        find_callers(pkg, name)


def _scenario_graph() -> None:
    """Import-graph build (should be unchanged — regression guard)."""
    clear_cache()
    GraphTool().execute(path=str(PKG), format="json")


def _scenario_analyze() -> None:
    """Raw package analysis (regression guard for the parse cache)."""
    analyze_package(PKG)


def main() -> None:
    print(f"axm-ast caller/graph benchmark — target: {PKG}")
    print()

    fp, count = _callers_fingerprint()
    print(f"fingerprint  sha256={fp}")
    print(f"             call_sites={count}")
    print()

    print("timings:")
    _time("analyze_package (raw parse)", _scenario_analyze)
    _time("graph build (cold)", _scenario_graph)
    _time("extract calls after analyze (cold)", _scenario_extract_only)
    _time("full cold caller pipeline", _scenario_cold_callers)

    # Isolated hot spot: re-extract calls with the package already analyzed.
    _recompute_setup()
    _time("re-extract calls (pkg warm) *", _scenario_recompute_calls, repeat=15)

    # find_callers over every symbol — linear scan vs indexed lookup.
    _query_setup()
    _time(
        f"find_callers x {len(_QUERY_NAMES)} symbols (warm)",
        _scenario_query_all_symbols,
        repeat=15,
    )
    print()
    print("  * isolates the redundant second parse the optimization removes")


if __name__ == "__main__":
    main()
