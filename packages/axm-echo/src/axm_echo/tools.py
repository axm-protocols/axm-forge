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
from typing import TYPE_CHECKING, TypedDict

from axm.tools.base import AXMTool, ToolResult

from axm_echo.cluster import (
    PAIR_THRESHOLD,
    Pair,
    cluster_pairs,
    cross_pairs,
    generic_docs,
    is_trivial_accessor,
    split_pairs,
)
from axm_echo.corpus import extract_monorepo
from axm_echo.embedding import embed, neighbors

if TYPE_CHECKING:
    from axm_echo.corpus import SymbolDict
    from axm_echo.embedding import Backend

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


class ClusterEntry(TypedDict):
    """A cross-package echo cluster (connected component of duplicate pairs)."""

    size: int
    score: float
    members: list[MemberEntry]


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


def _pair_entries(pairs: list[Pair], symbols: list[SymbolDict]) -> list[PairEntry]:
    """Serialize demoted pairs, strongest first."""
    ordered = sorted(pairs, key=lambda p: p[2], reverse=True)
    return [
        {"score": round(score, 4), "a": _member(symbols[i]), "b": _member(symbols[j])}
        for i, j, score in ordered
    ]


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
        **kwargs: object,
    ) -> ToolResult:
        """Cluster cross-package echoes over the configured corpus.

        Args:
            backend: Embedding backend -- ``"st"`` (neural MiniLM, default,
                requires the ``neural`` extra) or ``"tfidf"`` (pure CPU).
            threshold: Minimum cosine for a candidate pair.

        Returns:
            ToolResult with ``clusters`` (duplicate echoes), ``parallel_api``
            and ``boilerplate`` (demoted pairs), plus corpus counts.
        """
        try:
            return self._run(backend=backend, threshold=threshold)
        except Exception as exc:  # noqa: BLE001 — final tool boundary
            logger.warning("EchoCodeTool failed: %s", exc, exc_info=True)
            return ToolResult(success=False, error=str(exc))

    def _run(self, *, backend: Backend, threshold: float) -> ToolResult:
        """Execute the corpus -> embed -> pairs -> split -> cluster pipeline."""
        symbols = [
            s
            for s in extract_monorepo()
            if str(s.get("doc_full", "")).strip() and not is_trivial_accessor(s)
        ]
        if len(symbols) < _MIN_CORPUS:
            return ToolResult(
                success=True,
                data=self._empty_data(len(symbols)),
                text=self._render_text([], [], [], corpus=len(symbols)),
            )

        texts = [str(s["embed_text"]) for s in symbols]
        packages = [str(s["package"]) for s in symbols]
        matrix = embed(texts, backend=backend)

        pairs = cross_pairs(matrix, packages, threshold=threshold)
        generic = generic_docs(symbols)
        dupes, parallel, boilerplate = split_pairs(pairs, symbols, generic)

        clusters = self._build_clusters(dupes, symbols)
        parallel_entries = _pair_entries(parallel, symbols)
        boilerplate_entries = _pair_entries(boilerplate, symbols)

        data = {
            "corpus_size": len(symbols),
            "clusters": clusters,
            "parallel_api": parallel_entries,
            "boilerplate": boilerplate_entries,
        }
        text = self._render_text(
            clusters, parallel_entries, boilerplate_entries, corpus=len(symbols)
        )
        return ToolResult(success=True, data=data, text=text)

    @staticmethod
    def _empty_data(corpus_size: int) -> dict[str, object]:
        """The data payload for a corpus too small to compare."""
        return {
            "corpus_size": corpus_size,
            "clusters": [],
            "parallel_api": [],
            "boilerplate": [],
        }

    @staticmethod
    def _build_clusters(
        dupes: list[Pair], symbols: list[SymbolDict]
    ) -> list[ClusterEntry]:
        """Connected components of the duplicate pairs, serialized + scored."""
        components = cluster_pairs(dupes)
        clusters: list[ClusterEntry] = []
        for members in components:
            clusters.append(
                {
                    "size": len(members),
                    "score": round(_max_pair_score(members, dupes), 4),
                    "members": [_member(symbols[i]) for i in members],
                }
            )
        clusters.sort(key=lambda c: c["score"], reverse=True)
        return clusters

    @staticmethod
    def _render_text(
        clusters: list[ClusterEntry],
        parallel: list[PairEntry],
        boilerplate: list[PairEntry],
        *,
        corpus: int,
    ) -> str:
        """Render the echo report as compact text for token-efficient MCP output."""
        header = (
            f"echo_code | {len(clusters)} clusters | corpus {corpus} symbols | "
            f"{len(parallel)} parallel-API · {len(boilerplate)} boilerplate (demoted)"
        )
        if not clusters:
            return header
        lines = [header, ""]
        for idx, cluster in enumerate(clusters, start=1):
            lines.append(
                f"cluster {idx}  sim={cluster['score']:.3f}  "
                f"({cluster['size']} symbols)"
            )
            for member in cluster["members"]:
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
            backend: Embedding backend -- ``"st"`` (neural MiniLM, default,
                requires the ``neural`` extra) or ``"tfidf"`` (pure CPU).
            k: Maximum number of candidates to return.
            threshold: Minimum cosine for a candidate to be retrieved. Below it
                the candidate is dropped, so a novel intention returns an empty
                list rather than a spurious match (AC4).

        Returns:
            ToolResult with ``intention``, ``corpus_size`` and ``candidates``
            (ranked top-k, each carrying its docstrings and a location verdict).
        """
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
        if not intention.strip():
            raise ValueError("intention must be a non-empty string")

        symbols = [
            s
            for s in extract_monorepo()
            if str(s.get("doc_full", "")).strip() and not is_trivial_accessor(s)
        ]
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
