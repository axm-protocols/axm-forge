from __future__ import annotations

import re

from axm_audit.doc_gate.findings import DocGateFinding, FindingKind

__all__ = ["parse_mkdocs_output"]

_QUOTED = re.compile(r"'([^']*)'")

_DIAGNOSTIC = re.compile(r"^(?:WARNING|ERROR)\s+-\s+Doc file '[^']+'(?:\s|$)")

# Ordered keyword -> kind table. Order matters: a missing-anchor line also
# mentions "link", and an unknown-extension line also mentions "links", so the
# more specific keywords must be probed before the generic "link" fallback.
_KIND_KEYWORDS: tuple[tuple[str, FindingKind], ...] = (
    ("anchor", FindingKind.missing_anchor),
    ("extension", FindingKind.unknown_extension),
    ("reference", FindingKind.bad_reference),
    ("link", FindingKind.dead_link),
)


def _classify(lowered_line: str) -> FindingKind | None:
    for keyword, kind in _KIND_KEYWORDS:
        if keyword in lowered_line:
            return kind
    return None


def parse_mkdocs_output(output: str) -> list[DocGateFinding]:
    """Classify ``mkdocs build --strict`` log output into gate findings.

    Pure function: iterates the lines of ``output``, keeps only WARNING/ERROR
    lines that reference a documentation problem, and maps each to a
    :class:`DocGateFinding`. The referenced target and source page are recovered
    from the single-quoted tokens mkdocs emits (``Doc file 'PAGE' ... 'TARGET'``).

    Deterministic and free of I/O: the same ``output`` always yields the same
    list, and empty or clean output yields ``[]``.
    """
    findings: list[DocGateFinding] = []
    for raw in output.splitlines():
        line = raw.strip()
        if _DIAGNOSTIC.match(line) is None:
            continue
        kind = _classify(line.lower())
        if kind is None:
            continue
        quoted = _QUOTED.findall(line)
        source_page = quoted[0] if quoted else ""
        target = quoted[1] if len(quoted) > 1 else ""
        findings.append(
            DocGateFinding(kind=kind, target=target, source_page=source_page)
        )
    return findings
