"""Data models + module-wide constants for the fix pipeline."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

__all__ = [
    "CANONICAL_TIERS",
    "MAX_ITERATIONS",
    "NON_DETERMINISTIC_RULES",
    "TOP_K",
    "FileOp",
    "OpKind",
    "PipelineReport",
]


NON_DETERMINISTIC_RULES = frozenset(
    {
        # NO_PACKAGE_SYMBOL: a test that exercises no package symbol may
        # be a legitimate formal check on an artefact, or a candidate for
        # deletion. The verdict is context-dependent — use /scenario-rename
        # or inspect manually.
        "TEST_QUALITY_NO_PACKAGE_SYMBOL",
    }
)

CANONICAL_TIERS: frozenset[str] = frozenset({"unit", "integration", "e2e"})

MAX_ITERATIONS = 6
"""Hard cap on the fix pipeline's fixed-point loop.

The RELOCATE → SPLIT → MERGE → RENAME cascade mutates classification
(a moved test may change tier; a SPLIT may free a NAME_MISMATCH that
was hidden pre-split), so :func:`axm_audit.core.fix.run` re-runs the
stages until no new ops are planned. The cap fails loud on a buggy
fixed-point instead of looping forever.
"""

TOP_K = 2


OpKind = Literal["flatten", "relocate", "split", "merge", "rename"]
"""Stage tag for a planned :class:`FileOp`.

Mirrors the five mutating stages of the fix pipeline (FLATTEN, RELOCATE,
SPLIT, MERGE, RENAME). Stage 0.5 (non-canonical relocate) and stage 1.5
(layout flatten) emit warnings, not :class:`FileOp` entries.
"""


@dataclass
class FileOp:
    """A single planned filesystem mutation produced by the pipeline.

    ``target`` is a list only for SPLIT (one source → many targets); all
    other kinds use a single ``Path``. ``split_map`` is populated only
    when ``kind == "split"`` and maps each canonical target filename to
    the list of ``test_*`` symbols routed into it.
    """

    kind: OpKind
    source: Path
    target: Path | list[Path]
    rationale: str
    source_rule: str
    split_map: dict[str, list[str]] | None = None


@dataclass
class PipelineReport:
    """Aggregated output of :func:`axm_audit.core.fix.run`.

    ``ops`` lists every planned mutation across all fixed-point
    iterations. ``unfixable`` carries findings the pipeline declined to
    auto-resolve (e.g. ``TEST_QUALITY_NO_PACKAGE_SYMBOL``). ``applied``
    distinguishes dry-run from applied mode. ``warnings`` collects
    non-fatal messages from each stage and the post-pipeline polish.
    ``iterations`` records how many passes the fixed-point loop ran
    before convergence (1 in dry-run).
    """

    ops: list[FileOp] = field(default_factory=list)
    unfixable: list[dict[str, Any]] = field(default_factory=list)
    applied: bool = False
    warnings: list[str] = field(default_factory=list)
    iterations: int = 0

    def by_kind(self) -> dict[str, int]:
        """Return a count of planned ops grouped by :data:`OpKind`."""
        c: Counter[str] = Counter()
        for op in self.ops:
            c[op.kind] += 1
        return dict(c)
