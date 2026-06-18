"""Cross-package echo clustering + anti-signals (v7).

Ported from the dedup-detection POC ``poc_c3_docstring_pairs.py``: instead of
comparing function *bodies* (code <-> code) it compares their *promises* -- the
public docstrings -- across the whole monorepo, surfaces cross-package pairs
that are semantically close, and groups them into clusters.

The raw cross-package pairs are then split by the **v7 anti-signals** so the
duplicate clusters carry signal, not noise:

- **trivial accessors** -- a getter/setter promise (``Return the name.``) is
  boilerplate intent shared by every model; filtered up front (the POC's
  ``-96%`` noise cut).
- **parallel API** (AS2a/AS2b by name) -- a pair whose names start with their
  own package token (``excel_export`` / ``word_export``) is parallel-by-design,
  not copy-paste; demoted to the ``parallel_api`` bucket.
- **boilerplate frequency** -- a docstring first-line that recurs across many
  symbols (``CLI entry point.``) matches all its twins at ~1.0 without meaning
  duplication; demoted to the ``boilerplate`` bucket.

CALIBRATION (E3bis / AXM-2171, refine-loop, 2026-06): the two boilerplate
seuils were tuned against the real monorepo corpus (3.6k documented symbols).
``min_repeat=4`` catches the genuine mass-recurring promises (``CLI entry
point.`` 9x, ``main entry point.`` 5x, ``render the failure-path ...`` 10x,
the office table ops 4x) while leaving the 550+ unique terse promises and the
ground-truth duplicates (``RateLimitError``, ``request_with_retry``) alone; the
length floor stays at ``MIN_DOC_CHARS=15`` so a legitimate terse promise
(``APIUnavailable``, 38 chars) is never re-dropped. Two consecutive passes are
stable. The defaults below are the calibrated values, not raw POC ports.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from axm_echo.corpus import SymbolDict

import numpy as np

__all__ = [
    "MAX_CLUSTER_SIZE",
    "MIN_DOC_CHARS",
    "PAIR_THRESHOLD",
    "Pair",
    "SplitPairs",
    "cluster_pairs",
    "cross_pairs",
    "generic_docs",
    "is_parallel_api",
    "is_trivial_accessor",
    "split_pairs",
]

# Connected components larger than this are union-find over-merges, not echoes:
# empirically a genuine cross-package duplicate is 2-5 members, and the only
# >20-member component on the full monorepo galaxy (cluster 1673) was 100%
# noise (``main`` / ``render_text`` collapsed together). 50 is a comfortable
# margin; it is paramétrable per call so nothing is frozen.
MAX_CLUSTER_SIZE = 50

# Cosine threshold for a candidate duplicate pair. Calibrated in the POC:
# true MATCH intents land at 0.5-0.7, genuine NEW at <0.15. For docstring <->
# docstring (both sides real docstrings) the signal is stronger, so we sit high.
PAIR_THRESHOLD = 0.55

# Trivially-short docstrings ("Run.", "TODO") are floor-filtered; the real
# boilerplate filter is corpus-frequency (see ``generic_docs``). Calibrated
# floor (E3bis/AXM-2171): 15 chars keeps every unique terse legit promise
# (``APIUnavailable``, 38 chars) -- a higher floor re-drops them (POC bug).
MIN_DOC_CHARS = 15

# A pair: (index_a, index_b, cosine_similarity) over the symbol corpus.
type Pair = tuple[int, int, float]

# The three buckets a raw cross-package pair is split into.
type SplitPairs = tuple[list[Pair], list[Pair], list[Pair]]

# Workspace tokens: a symbol whose name starts with its own package token is a
# parallel API surface, not a duplicate (AS2a). Mirrors v7 AS2 at the pair level.
_WS_TOKENS = frozenset(
    {
        "excel",
        "ppt",
        "word",
        "office",
        "mail",
        "n8n",
        "scheduler",
        "bench",
        "runner",
        "ast",
        "init",
        "audit",
        "git",
        "smelt",
        "bib",
        "market",
        "screener",
        "sentiment",
        "backtest",
        "broker",
        "portfolio",
        "anvil",
        "commons",
        "edit",
        "formal",
        "cloudflare",
        "mlx",
        "imessage",
        "quizz",
        "vscode",
        "ticket",
        "weather",
        "route",
        "discover",
        "echo",
        "warden",
        "harness",
        "llm",
        "train",
        "dag",
        "engine",
        "loom",
        "nexus",
        "protocols",
        "latex",
        "fig",
        "stealthwright",
        "travel",
        "kdeeb",
    }
)

# A docstring promise that is a bare attribute accessor: "Return the name.",
# "Get the value", "Set the path." -- boilerplate intent every model shares.
_ACCESSOR_DOC_RE = re.compile(
    r"^(return|returns|get|gets|set|sets)\b.{0,40}$", re.IGNORECASE
)
# Common accessor symbol names (a getter/setter property surface).
_ACCESSOR_NAMES = frozenset(
    {"name", "value", "id", "key", "path", "data", "kind", "type", "label"}
)


def _doc_first_line(sym: SymbolDict) -> str:
    """The symbol's docstring first line, lowercased and stripped."""
    return str(sym.get("doc_first_line", "")).strip()


def is_trivial_accessor(sym: SymbolDict) -> bool:
    """Whether *sym* is a trivial getter/setter accessor (filtered, AC3).

    Trivial accessors are the dominant noise source in cross-package
    docstring matching: every model declares ``Return the name.`` and they
    all match each other at ~1.0 without being duplicate *behaviour*. We
    detect them on the available projection -- an accessor-shaped docstring
    first line, or an accessor symbol name paired with a terse promise.
    """
    first = _doc_first_line(sym)
    if _ACCESSOR_DOC_RE.match(first):
        return True
    name = str(sym.get("name", ""))
    return name in _ACCESSOR_NAMES and len(first) < MIN_DOC_CHARS * 2


def is_parallel_api(a: SymbolDict, b: SymbolDict) -> bool:
    """Whether the pair is a parallel API surface, not a duplicate (AS2a/AS2b).

    A symbol whose name starts with its own package token (``excel_export``
    in ``axm-excel``, ``word_export`` in ``axm-word``) is parallel-by-design.
    If either side of the pair matches its package token, demote the pair.
    """
    for sym in (a, b):
        short = str(sym.get("package", "")).removeprefix("axm-")
        toks = str(sym.get("name", "")).lstrip("_").split("_")
        if short in _WS_TOKENS and toks and toks[0] == short:
            return True
    return False


def generic_docs(symbols: list[SymbolDict], *, min_repeat: int = 4) -> set[str]:
    """First-lines recurring across ``>= min_repeat`` symbols are boilerplate.

    LESSON (POC, 2026-06): a brute length filter wrongly dropped a legitimate
    terse promise (``APIUnavailable``, 38 chars). Corpus FREQUENCY is the right
    signal -- a first-line shared by many symbols is boilerplate, a unique terse
    line is not. Length stays only as a floor (``MIN_DOC_CHARS``).
    """
    counts: dict[str, int] = defaultdict(int)
    for sym in symbols:
        key = _doc_first_line(sym).lower()
        if key:
            counts[key] += 1
    return {k for k, c in counts.items() if c >= min_repeat}


def cross_pairs(
    matrix: NDArray[np.float64], packages: list[str], *, threshold: float
) -> list[Pair]:
    """Cross-package candidate pairs above ``threshold`` (brute-force matmul).

    Compares every embedded row against every other in batched dot products,
    keeping only the upper triangle and only pairs whose two symbols live in
    *different* packages (same-package echoes are out of scope).

    Args:
        matrix: ``(n, dim)`` row-normalized embedding matrix.
        packages: Per-row package name, parallel to ``matrix`` rows.
        threshold: Minimum cosine to keep a pair.

    Returns:
        ``(i, j, cosine)`` triples with ``i < j`` and distinct packages.
    """
    pairs: list[Pair] = []
    n = matrix.shape[0]
    batch = 256
    for start in range(0, n, batch):
        end = min(n, start + batch)
        block = matrix[start:end] @ matrix.T
        for li in range(block.shape[0]):
            gi = start + li
            row = block[li].copy()
            row[gi] = 0.0
            for raw in np.where(row >= threshold)[0]:
                gj = int(raw)
                if gj <= gi or packages[gi] == packages[gj]:
                    continue
                pairs.append((gi, gj, float(row[gj])))
    return pairs


def split_pairs(
    pairs: list[Pair], symbols: list[SymbolDict], generic: set[str]
) -> SplitPairs:
    """Split raw cross-package pairs into (dupes, parallel, boilerplate).

    Applies the v7 anti-signals: a pair whose *both* sides are boilerplate
    (generic first-line or trivially short doc) is boilerplate; a name-parallel
    pair is parallel API; everything else is a genuine duplicate candidate.
    """
    dupes: list[Pair] = []
    parallel: list[Pair] = []
    boilerplate: list[Pair] = []
    for gi, gj, score in pairs:
        a, b = symbols[gi], symbols[gj]
        if _both_boilerplate(a, b, generic):
            boilerplate.append((gi, gj, score))
        elif is_parallel_api(a, b):
            parallel.append((gi, gj, score))
        else:
            dupes.append((gi, gj, score))
    return dupes, parallel, boilerplate


def _is_boilerplate(sym: SymbolDict, generic: set[str]) -> bool:
    """Whether *sym* carries a boilerplate promise (generic, terse, accessor)."""
    first = _doc_first_line(sym).lower()
    doc_full = str(sym.get("doc_full", ""))
    return first in generic or len(doc_full) < MIN_DOC_CHARS or is_trivial_accessor(sym)


def _both_boilerplate(a: SymbolDict, b: SymbolDict, generic: set[str]) -> bool:
    """Whether both sides of a pair are boilerplate (then the pair is noise)."""
    return _is_boilerplate(a, generic) and _is_boilerplate(b, generic)


def cluster_pairs(
    pairs: list[Pair], *, max_cluster_size: int = MAX_CLUSTER_SIZE
) -> list[list[int]]:
    """Group pairs into connected components (clusters of echoing symbols).

    Each duplicate pair is an edge; the connected components of the resulting
    graph are the echo clusters. Returns one sorted index list per cluster,
    largest first, so a triple of mutually-duplicate symbols lands in a single
    cluster rather than three disjoint pairs.

    A component with more than ``max_cluster_size`` members is **dropped**: such
    a mega-cluster is a union-find over-merge (a structural-conformity signal),
    not a genuine duplicate echo. The bound is paramétrable; the default is
    :data:`MAX_CLUSTER_SIZE`.

    Args:
        pairs: Duplicate ``(i, j, score)`` edges.
        max_cluster_size: Reject any component strictly larger than this.

    Returns:
        One sorted index list per surviving cluster, largest first.
    """
    parent: dict[int, int] = {}

    def find(x: int) -> int:
        parent.setdefault(x, x)
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    for gi, gj, _score in pairs:
        union(gi, gj)

    groups: dict[int, list[int]] = defaultdict(list)
    for node in parent:
        groups[find(node)].append(node)
    clusters = [
        sorted(members)
        for members in groups.values()
        if len(members) <= max_cluster_size
    ]
    clusters.sort(key=len, reverse=True)
    return clusters
