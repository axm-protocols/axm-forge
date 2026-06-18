"""``echo_code`` AXMTool -- cross-package echo detection over a corpus.

A read-only AXMTool in the spirit of ``ast_dead_code`` (see
``axm_ast/tools/dead_code.py``): it walks the configured monorepo scope,
embeds every public documented symbol, finds cross-package pairs whose
*promises* (docstrings) are semantically close, applies the v7 anti-signals,
and returns the surviving **duplicate clusters** plus the demoted
parallel-API / boilerplate buckets.

Registered under the ``axm.tools`` entry point, so it is reachable as an MCP
tool, an ``axm echo_code`` CLI command, and a DAG ``tool_node`` for free
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
from axm_echo.embedding import embed

if TYPE_CHECKING:
    from axm_echo.corpus import SymbolDict
    from axm_echo.embedding import Backend

logger = logging.getLogger(__name__)

__all__ = ["ClusterEntry", "EchoCodeTool", "MemberEntry", "PairEntry"]

# A cross-package comparison needs at least two documented symbols.
_MIN_CORPUS = 2


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
