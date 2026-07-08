"""echo AXMTools -- cross-package echo detection and intent retrieval.

Two read-only AXMTools in the spirit of ``ast_dead_code`` (see
``axm_ast/tools/dead_code.py``), sharing the corpus -> embed pipeline:

* :class:`EchoCodeTool` (``echo_code``) walks the configured monorepo scope,
  embeds every public documented symbol, finds cross-package pairs whose
  *promises* (docstrings) are semantically close, applies the v7 anti-signals,
  and returns the surviving **duplicate clusters** plus the demoted
  parallel-API / boilerplate buckets.
* :class:`EchoCheckTool` (``echo_check``) embeds a free-form *intention* and
  retrieves the top-k nearest public symbols across the whole monorepo, each
  tagged with a location verdict (reuse canonical / reuse in place /
  promotable). It does the *retrieval*, never the use/extend/nothing decision
  -- that is left to the calling agent.

Both are registered under the ``axm.tools`` entry point, so each is reachable
as an MCP tool, an ``axm <name>`` CLI command, and a DAG ``tool_node`` for free
(one declaration, three surfaces).
"""

from __future__ import annotations

import logging
import tomllib
from typing import TYPE_CHECKING, TypedDict, cast

from axm.tools.base import AXMTool, ToolResult

from axm_echo.cluster import (
    MAX_CLUSTER_SIZE,
    PAIR_THRESHOLD,
    Pair,
    cluster_pairs,
    cross_pairs,
    generic_docs,
    is_trivial_accessor,
    split_pairs,
)
from axm_echo.corpus import extract_monorepo
from axm_echo.embedding import Backend, embed, neighbors
from axm_echo.scope import load_scope
from axm_echo.waiver import (
    cluster_hash,
    extract_acknowledged_section,
    mark_acknowledged,
    stale_acknowledged,
    validate_acknowledged_entry,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from axm_echo.corpus import SymbolDict

logger = logging.getLogger(__name__)

__all__ = [
    "CandidateEntry",
    "ClusterEntry",
    "EchoCheckTool",
    "EchoCodeTool",
    "MemberEntry",
    "PairEntry",
]

# A cross-package comparison needs at least two documented symbols.
_MIN_CORPUS = 2

# The report bounds its output to the top-N nearest *non-acknowledged* clusters;
# the neural pass still finds them all, only the display is bounded. The total
# count stays visible. Paramétrable on the tool.
_DEFAULT_TOP_N = 30

# The demoted buckets (parallel-API, boilerplate) are unbounded noise: on a
# large corpus a single repeated boilerplate promise produces ~k^2/2 pairs at
# cosine ~1.0. Serializing them whole would blow the MCP transport chunk
# budget (the ``ast_describe(detail='full')`` failure mode). Bound each bucket
# in ``data`` to its strongest entries; the true count stays visible.
_MAX_DEMOTED_PAIRS = 50

# echo_code identifies a cluster member by its (package, qualname). The waiver
# hash is computed over this key schema (duplicate_tests uses (file, name)).
_ECHO_KEY_FIELDS = ("package", "qualname")

# The acknowledged-waiver section is ``[[tool.axm-echo.acknowledged]]``.
_WAIVER_TOOL = "axm-echo"
_WAIVER_RULE = "acknowledged"

# The canonical commons package: a candidate already here is canonical.
_INGOT_PACKAGE = "axm-ingot"

# Retrieval defaults for echo_check.
_CHECK_TOP_K = 10
_CHECK_THRESHOLD = 0.30

# A docstring this long signals a documented, general-purpose helper -- the
# kind of symbol worth promoting into the ingot (a canonisable signal).
_PROMOTABLE_DOC_CHARS = 40


class MemberEntry(TypedDict):
    """A serialized symbol inside a cluster or a demoted pair."""

    qualname: str
    name: str
    package: str
    doc_first_line: str
    path: str
    line: int


class ClusterEntry(TypedDict, total=False):
    """A cross-package echo cluster (connected component of duplicate pairs).

    ``cluster_hash`` is the waiver address over the members' ``(package,
    qualname)``; ``acknowledged`` is stamped when a live cluster is waived.
    Both are added during the run, hence ``total=False``.
    """

    size: int
    score: float
    members: list[MemberEntry]
    cluster_hash: str
    acknowledged: bool


class PairEntry(TypedDict):
    """A demoted cross-package pair (parallel-API or boilerplate)."""

    score: float
    a: MemberEntry
    b: MemberEntry


class CandidateEntry(TypedDict):
    """A retrieved symbol matching an intention, with its location verdict.

    The ``verdict`` is purely a *location* tag (AC3) -- it never encodes a
    use/extend/nothing decision (AC4): a high score does not mean "use this",
    only "this is the closest existing promise". ``promotable`` flags a
    non-ingot candidate documented well enough to be worth canonicalising.
    """

    score: float
    verdict: str
    promotable: bool
    qualname: str
    name: str
    package: str
    doc_first_line: str
    doc_full: str
    path: str
    line: int


def _member(sym: SymbolDict) -> MemberEntry:
    """Project a corpus symbol onto the serialized member view."""
    return {
        "qualname": str(sym.get("qualname", "")),
        "name": str(sym.get("name", "")),
        "package": str(sym.get("package", "")),
        "doc_first_line": str(sym.get("doc_first_line", "")),
        "path": str(sym.get("path", "")),
        "line": int(sym.get("line", 0) or 0),
    }


def _max_pair_score(members: list[int], pairs: list[Pair]) -> float:
    """The strongest cosine among pairs internal to a cluster's members."""
    member_set = set(members)
    scores = [s for i, j, s in pairs if i in member_set and j in member_set]
    return max(scores) if scores else 0.0


def _pair_entries(
    pairs: list[Pair], symbols: list[SymbolDict], *, limit: int = _MAX_DEMOTED_PAIRS
) -> list[PairEntry]:
    """Serialize the ``limit`` strongest demoted pairs (bounded for MCP payload)."""
    ordered = sorted(pairs, key=lambda p: p[2], reverse=True)[:limit]
    return [
        {"score": round(score, 4), "a": _member(symbols[i]), "b": _member(symbols[j])}
        for i, j, score in ordered
    ]


def _documented_corpus(*, drop_accessors: bool) -> list[SymbolDict]:
    """The documented monorepo corpus shared by both tools.

    Keeps only symbols carrying a real docstring (``doc_full``). ``echo_code``
    (dedup) additionally drops trivial accessors -- the POC's calibrated -96%
    noise cut for cross-package *clustering*. ``echo_check`` (retrieval) keeps
    them: a terse but reusable helper (``Return the slugified string.``) must
    stay findable, and the 0.30 retrieval threshold already screens noise, so
    filtering it here would silently hide canonical helpers and mint the very
    duplicates the tool exists to prevent.
    """
    return [
        s
        for s in extract_monorepo()
        if str(s.get("doc_full", "")).strip()
        and not (drop_accessors and is_trivial_accessor(s))
    ]


def _read_acknowledged_section(scan_root: Path) -> object:
    """Read the ``[[tool.axm-echo.acknowledged]]`` section of a scan-root pyproject.

    Returns the raw section value (a list of waiver tables when present),
    degrading to ``{}`` when the pyproject is absent, unreadable, or invalid TOML
    -- the read never raises.
    """
    pyproject = scan_root / "pyproject.toml"
    try:
        raw = pyproject.read_bytes()
    except OSError:
        return {}
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):
        return {}
    return extract_acknowledged_section(data, tool=_WAIVER_TOOL, rule=_WAIVER_RULE)


def _partition_waivers(section: object) -> tuple[list[dict[str, str]], list[str]]:
    """Split a raw acknowledged section into valid waivers and schema errors.

    Each entry is validated by :func:`validate_acknowledged_entry`; valid ones
    are normalized to ``{"hash", "reason"}`` dicts, invalid ones contribute a
    message. A non-list section (schema misuse) yields a single error.
    """
    if not isinstance(section, list):
        if section in ({}, None):
            return [], []
        return [], ["acknowledged section must be an array of tables (schema error)"]
    valid: list[dict[str, str]] = []
    errors: list[str] = []
    for entry in section:
        error = validate_acknowledged_entry(entry)
        if error is not None:
            errors.append(error)
            continue
        valid.append({"hash": str(entry["hash"]), "reason": str(entry["reason"])})
    return valid, errors


class EchoCodeTool(AXMTool):
    """Detect cross-package code echoes (intent-equivalent duplicates).

    Registered as ``echo_code`` via the ``axm.tools`` entry point.
    """

    agent_hint = (
        "Find intent-equivalent duplicate symbols across packages (clusters "
        "from cross-package docstring similarity, anti-signals applied)."
    )
    domain = "echo"
    tags = frozenset({"duplicate", "similarity", "echo", "clustering"})

    @property
    def name(self) -> str:
        """Return the tool name for registry lookup."""
        return "echo_code"

    def execute(
        self,
        *,
        backend: Backend = "st",
        threshold: float = PAIR_THRESHOLD,
        top_n: int = _DEFAULT_TOP_N,
        max_cluster_size: int = MAX_CLUSTER_SIZE,
        **kwargs: object,
    ) -> ToolResult:
        """Cluster cross-package echoes over the configured corpus.

        Args:
            backend: Embedding backend -- ``"st"`` (neural MiniLM, the
                in-process default) or ``"tfidf"`` (pure CPU, no torch).
            threshold: Minimum cosine for a candidate pair.
            top_n: Show at most this many of the nearest *non-acknowledged*
                clusters; the total count stays visible in the metadata.
            max_cluster_size: Reject components larger than this as union-find
                over-merges (structural conformity, not a duplicate echo).

        Returns:
            ToolResult with the bounded ``clusters`` (each carrying a
            ``cluster_hash``), ``parallel_api`` and ``boilerplate`` (demoted
            pairs), the live/shown/actionable counts, and ``stale_acknowledged``.
        """
        if backend not in ("st", "tfidf"):
            return ToolResult(
                success=False,
                error=f"Invalid backend {backend!r}; must be 'st' or 'tfidf'",
            )
        if not 0.0 <= threshold <= 1.0:
            return ToolResult(
                success=False,
                error=f"threshold must be a cosine in [0.0, 1.0], got {threshold}",
            )
        if top_n < 1:
            return ToolResult(success=False, error=f"top_n must be >= 1, got {top_n}")
        if max_cluster_size < 1:
            return ToolResult(
                success=False,
                error=f"max_cluster_size must be >= 1, got {max_cluster_size}",
            )

        try:
            return self._run(
                backend=backend,
                threshold=threshold,
                top_n=top_n,
                max_cluster_size=max_cluster_size,
            )
        except Exception as exc:  # noqa: BLE001 — final tool boundary
            logger.warning("EchoCodeTool failed: %s", exc, exc_info=True)
            return ToolResult(
                success=False,
                error=str(exc),
                hint=(
                    "Clustering failed over the monorepo corpus. Retry with "
                    "backend='tfidf' (no torch) if the neural backend is "
                    "unavailable, or check the corpus is reachable."
                ),
            )

    def _run(
        self,
        *,
        backend: Backend,
        threshold: float,
        top_n: int,
        max_cluster_size: int,
    ) -> ToolResult:
        """Execute the corpus -> embed -> pairs -> split -> cluster pipeline."""
        symbols = _documented_corpus(drop_accessors=True)
        if len(symbols) < _MIN_CORPUS:
            return ToolResult(
                success=True,
                data=self._empty_data(len(symbols)),
                text=self._render_text(
                    [],
                    [],
                    [],
                    corpus=len(symbols),
                    counts={"total": 0, "actionable": 0, "stale": 0},
                ),
            )

        texts = [str(s["embed_text"]) for s in symbols]
        packages = [str(s["package"]) for s in symbols]
        matrix = embed(texts, backend=backend)

        pairs = cross_pairs(matrix, packages, threshold=threshold)
        generic = generic_docs(symbols)
        dupes, parallel, boilerplate = split_pairs(pairs, symbols, generic)

        clusters = self._build_clusters(dupes, symbols, max_cluster_size)
        waivers, waiver_errors = self._load_waivers()
        mark_acknowledged(clusters, waivers)
        stale = stale_acknowledged(clusters, waivers)

        actionable = [c for c in clusters if not c.get("acknowledged")]
        shown = actionable[:top_n]
        parallel_entries = _pair_entries(parallel, symbols)
        boilerplate_entries = _pair_entries(boilerplate, symbols)

        data = {
            "corpus_size": len(symbols),
            "clusters": shown,
            "cluster_count": len(clusters),
            "actionable_count": len(actionable),
            "shown_count": len(shown),
            "parallel_api": parallel_entries,
            "parallel_api_count": len(parallel),
            "boilerplate": boilerplate_entries,
            "boilerplate_count": len(boilerplate),
            "stale_acknowledged": stale,
            "acknowledged_errors": waiver_errors,
        }
        text = self._render_text(
            shown,
            parallel_entries,
            boilerplate_entries,
            corpus=len(symbols),
            counts={
                "total": len(clusters),
                "actionable": len(actionable),
                "stale": len(stale),
                "parallel_total": len(parallel),
                "boilerplate_total": len(boilerplate),
            },
        )
        return ToolResult(success=True, data=data, text=text)

    @staticmethod
    def _load_waivers() -> tuple[list[dict[str, str]], list[str]]:
        """Read ``[[tool.axm-echo.acknowledged]]`` from the scan-root pyproject.

        The waiver lives in the pyproject of the *scan root* -- the first
        :func:`load_scope` root (a documented ownership choice for the
        cross-package case; cf. SPEC-similarity-echo §5bis). Each entry is
        validated; malformed entries are skipped and reported, never raised.

        Returns:
            ``(valid_waivers, errors)`` where each valid waiver is a
            ``{"hash", "reason"}`` dict and ``errors`` lists schema messages.
        """
        roots = load_scope()
        if not roots:
            return [], []
        section = _read_acknowledged_section(roots[0])
        return _partition_waivers(section)

    @staticmethod
    def _empty_data(corpus_size: int) -> dict[str, object]:
        """The data payload for a corpus too small to compare."""
        return {
            "corpus_size": corpus_size,
            "clusters": [],
            "cluster_count": 0,
            "actionable_count": 0,
            "shown_count": 0,
            "parallel_api": [],
            "parallel_api_count": 0,
            "boilerplate": [],
            "boilerplate_count": 0,
            "stale_acknowledged": [],
            "acknowledged_errors": [],
        }

    @staticmethod
    def _build_clusters(
        dupes: list[Pair], symbols: list[SymbolDict], max_cluster_size: int
    ) -> list[dict[str, object]]:
        """Connected components of the duplicate pairs, serialized + scored.

        Each serialized cluster carries a ``cluster_hash`` over its members'
        ``(package, qualname)`` so the waiver mechanism can address it.
        """
        components = cluster_pairs(dupes, max_cluster_size=max_cluster_size)
        clusters: list[dict[str, object]] = []
        for members in components:
            entry: dict[str, object] = {
                "size": len(members),
                "score": round(_max_pair_score(members, dupes), 4),
                "members": [_member(symbols[i]) for i in members],
            }
            entry["cluster_hash"] = cluster_hash(entry, key_fields=_ECHO_KEY_FIELDS)
            clusters.append(entry)
        clusters.sort(key=lambda c: cast("float", c["score"]), reverse=True)
        return clusters

    @staticmethod
    def _render_text(
        clusters: list[dict[str, object]],
        parallel: list[PairEntry],
        boilerplate: list[PairEntry],
        *,
        corpus: int,
        counts: Mapping[str, int],
    ) -> str:
        """Render the echo report as compact text for token-efficient MCP output.

        ``counts`` carries ``total`` (live clusters), ``actionable`` (live
        non-acknowledged) and ``stale`` (orphan waivers) for the header.
        """
        total = counts.get("total", 0)
        actionable = counts.get("actionable", 0)
        stale = counts.get("stale", 0)
        header = (
            f"echo_code | {total} clusters, {len(clusters)} shown "
            f"({actionable} actionable) | corpus {corpus} symbols | "
            f"{len(parallel)} parallel-API · {len(boilerplate)} boilerplate (demoted)"
        )
        if stale:
            header += f" | {stale} stale waiver(s)"
        parallel_total = counts.get("parallel_total", len(parallel))
        boilerplate_total = counts.get("boilerplate_total", len(boilerplate))
        if parallel_total > len(parallel) or boilerplate_total > len(boilerplate):
            header += (
                f" | demoted shown {len(parallel)}/{parallel_total} parallel · "
                f"{len(boilerplate)}/{boilerplate_total} boilerplate"
            )
        if not clusters:
            return header
        lines = [header, ""]
        for idx, cluster in enumerate(clusters, start=1):
            lines.append(
                f"cluster {idx}  sim={cast('float', cluster['score']):.3f}  "
                f"({cluster['size']} symbols)"
            )
            members = cluster["members"]
            if not isinstance(members, list):
                continue
            for member in members:
                lines.append(
                    f"  {member['qualname']}  [{member['package']}]  "
                    f"“{member['doc_first_line']}”"
                )
        return "\n".join(lines)


def _verdict_for(package: str) -> str:
    """The location verdict for a candidate found in *package* (AC3).

    ``axm-ingot`` is the canonical commons, so a hit there is "reuse the
    canonical symbol"; anything else is "reuse it in place" -- we never hide a
    real helper just because it has not been canonicalised yet (that absence is
    exactly what floods the promotion backlog when the ingot is empty).
    """
    return "reuse_canonical" if package == _INGOT_PACKAGE else "reuse_in_place"


def _candidate(sym: SymbolDict, score: float) -> CandidateEntry:
    """Project a retrieved corpus symbol onto the serialized candidate view."""
    package = str(sym.get("package", ""))
    doc_full = str(sym.get("doc_full", ""))
    promotable = package != _INGOT_PACKAGE and len(doc_full.strip()) >= (
        _PROMOTABLE_DOC_CHARS
    )
    return {
        "score": round(score, 4),
        "verdict": _verdict_for(package),
        "promotable": promotable,
        "qualname": str(sym.get("qualname", "")),
        "name": str(sym.get("name", "")),
        "package": package,
        "doc_first_line": str(sym.get("doc_first_line", "")),
        "doc_full": doc_full,
        "path": str(sym.get("path", "")),
        "line": int(sym.get("line", 0) or 0),
    }


class EchoCheckTool(AXMTool):
    """Retrieve the public symbols closest to a free-form *intention*.

    Registered as ``echo_check`` via the ``axm.tools`` entry point. It embeds
    the intention, retrieves the top-k nearest documented symbols across the
    whole monorepo corpus (AC2), and tags each with a location verdict (AC3).
    Retrieval is decoupled from the use/extend/nothing decision (AC4): the tool
    returns ranked candidates + docstrings and leaves the call to the agent.
    """

    agent_hint = (
        "Before writing a helper, retrieve the closest existing symbols across "
        "the monorepo for an intention (top-k + docstrings + reuse/promote "
        "verdict). Decide use/extend/nothing yourself -- this only ranks."
    )
    domain = "echo"
    tags = frozenset({"reuse", "similarity", "echo", "retrieval"})

    @property
    def name(self) -> str:
        """Return the tool name for registry lookup."""
        return "echo_check"

    def execute(
        self,
        *,
        intention: str = "",
        backend: Backend = "st",
        k: int = _CHECK_TOP_K,
        threshold: float = _CHECK_THRESHOLD,
        **kwargs: object,
    ) -> ToolResult:
        """Retrieve the top-k symbols closest to *intention* over the corpus.

        Args:
            intention: Free-form description of the behaviour to implement.
            backend: Embedding backend -- ``"st"`` (neural MiniLM, the
                in-process default) or ``"tfidf"`` (pure CPU, no torch).
            k: Maximum number of candidates to return.
            threshold: Minimum cosine for a candidate to be retrieved. Below it
                the candidate is dropped, so a novel intention returns an empty
                list rather than a spurious match (AC4).

        Returns:
            ToolResult with ``intention``, ``corpus_size`` and ``candidates``
            (ranked top-k, each carrying its docstrings and a location verdict).
        """
        if backend not in ("st", "tfidf"):
            return ToolResult(
                success=False,
                error=f"Invalid backend {backend!r}; must be 'st' or 'tfidf'",
            )
        if k < 1:
            return ToolResult(success=False, error=f"k must be >= 1, got {k}")
        if not 0.0 <= threshold <= 1.0:
            return ToolResult(
                success=False,
                error=f"threshold must be a cosine in [0.0, 1.0], got {threshold}",
            )
        if not intention.strip():
            return ToolResult(
                success=False, error="intention must be a non-empty string"
            )
        try:
            return self._run(
                intention=intention, backend=backend, k=k, threshold=threshold
            )
        except Exception as exc:  # noqa: BLE001 — final tool boundary
            logger.warning("EchoCheckTool failed: %s", exc, exc_info=True)
            return ToolResult(success=False, error=str(exc))

    def _run(
        self, *, intention: str, backend: Backend, k: int, threshold: float
    ) -> ToolResult:
        """Execute the corpus -> embed -> retrieve -> verdict pipeline."""
        symbols = _documented_corpus(drop_accessors=False)
        if not symbols:
            return ToolResult(
                success=True,
                data={"intention": intention, "corpus_size": 0, "candidates": []},
                text=self._render_text(intention, [], corpus=0),
            )

        texts = [str(s["embed_text"]) for s in symbols]
        matrix = embed([intention, *texts], backend=backend)
        hits = neighbors(matrix[0], matrix[1:], k=k, threshold=threshold)

        candidates = [_candidate(symbols[idx], score) for idx, score in hits]
        data = {
            "intention": intention,
            "corpus_size": len(symbols),
            "candidates": candidates,
        }
        text = self._render_text(intention, candidates, corpus=len(symbols))
        return ToolResult(success=True, data=data, text=text)

    @staticmethod
    def _render_text(
        intention: str, candidates: list[CandidateEntry], *, corpus: int
    ) -> str:
        """Render the retrieval report as compact, token-efficient text."""
        header = (
            f"echo_check | “{intention}” | {len(candidates)} candidates | "
            f"corpus {corpus} symbols"
        )
        if not candidates:
            return f"{header}\n(no candidate above threshold — likely novel)"
        lines = [header, ""]
        for rank, cand in enumerate(candidates, start=1):
            promote = " (promotable→ingot)" if cand["promotable"] else ""
            lines.append(
                f"{rank}. {cand['qualname']}  [{cand['package']}]  "
                f"sim={cand['score']:.3f}  {cand['verdict']}{promote}"
            )
            lines.append(f'   "{cand["doc_first_line"]}"')
        return "\n".join(lines)
