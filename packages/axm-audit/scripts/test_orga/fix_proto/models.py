"""Data models + module-wide constants for the fix pipeline."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

__all__ = [
    "FileOp",
    "OpKind",
    "PipelineReport",
    "NON_DETERMINISTIC_RULES",
    "CANONICAL_TIERS",
    "MAX_ITERATIONS",
    "TOP_K",
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

TOP_K = 2


OpKind = Literal["flatten", "relocate", "split", "merge", "rename"]


@dataclass
class FileOp:
    kind: OpKind
    source: Path
    target: Path | list[Path]
    rationale: str
    source_rule: str
    # SPLIT: tuple keyed by the canonical filename a test belongs to →
    # list of test_* names that should land in that file.
    split_map: dict[str, list[str]] | None = None


@dataclass
class PipelineReport:
    ops: list[FileOp] = field(default_factory=list)
    unfixable: list[dict[str, Any]] = field(default_factory=list)
    applied: bool = False
    warnings: list[str] = field(default_factory=list)
    iterations: int = 0

    def by_kind(self) -> dict[str, int]:
        c: Counter[str] = Counter()
        for op in self.ops:
            c[op.kind] += 1
        return dict(c)
