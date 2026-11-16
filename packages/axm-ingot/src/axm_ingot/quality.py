"""Explicit provenance for measurements of an isolated Git revision."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class QualityOrigin:
    """Identity of the source package and the Git revision actually measured."""

    path: Path
    sha: str
    branch: str

    def __post_init__(self) -> None:
        if not self.path.is_absolute() or self.path != self.path.resolve():
            raise ValueError("quality origin path must be absolute and canonical")
        if re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", self.sha) is None:
            raise ValueError("quality origin sha must be a full Git object id")
        if not self.branch.strip() or self.branch != self.branch.strip():
            raise ValueError("quality origin branch must be nonempty")
        if any(character in self.branch for character in ("\n", "\r", "\0")):
            raise ValueError("quality origin branch contains a control character")

    @classmethod
    def from_data(cls, value: Mapping[str, str] | None) -> QualityOrigin | None:
        """Validate a transport payload without inferring a source from an export."""
        if value is None:
            return None
        if set(value) != {"path", "sha", "branch"}:
            raise ValueError("quality origin requires exactly path, sha and branch")
        if not all(isinstance(item, str) for item in value.values()):
            raise ValueError("quality origin values must be strings")
        return cls(Path(value["path"]), value["sha"], value["branch"])
