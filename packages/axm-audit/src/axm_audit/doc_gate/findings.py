from __future__ import annotations

import enum

from pydantic import BaseModel, ConfigDict

__all__ = ["DocGateFinding", "FindingKind"]


class FindingKind(enum.StrEnum):
    """Kinds of documentation-gate findings.

    A ``StrEnum`` whose members compare equal to their string value, e.g.
    ``FindingKind.dead_link == "dead_link"``.
    """

    dead_link = "dead_link"
    missing_anchor = "missing_anchor"
    unknown_extension = "unknown_extension"
    bad_reference = "bad_reference"


class DocGateFinding(BaseModel):  # type: ignore[explicit-any]
    """A single finding emitted by the documentation gate.

    Records the kind of issue, the referenced target, and the page on which
    the reference was found. Rejects unknown extra fields (``extra='forbid'``).
    """

    model_config = ConfigDict(extra="forbid")

    kind: FindingKind
    target: str
    source_page: str
