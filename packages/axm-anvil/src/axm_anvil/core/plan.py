"""Move plan dataclass and related exceptions."""

from __future__ import annotations

from dataclasses import dataclass, field

from axm_anvil.core.callers import CallerRewrite

__all__ = [
    "CallerRewrite",
    "ImportCycleError",
    "MovePlan",
    "MoveValidationError",
    "OverloadPartialMoveError",
    "SharedHelperDetection",
    "SharedHelpersError",
    "SymbolAlreadyExistsError",
    "SymbolNotFoundError",
]


class ImportCycleError(Exception):
    """Raised when a move would introduce a new import cycle."""

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = list(cycle)
        chain = " \u2192 ".join([*self.cycle, self.cycle[0]])
        super().__init__(f"Import cycle: {chain}")


class SymbolNotFoundError(Exception):
    """Raised when a requested symbol does not exist in the source module."""


class SymbolAlreadyExistsError(Exception):
    """Raised when a requested symbol already exists in the target module."""


class OverloadPartialMoveError(Exception):
    """Raised when only a subset of an overload group is requested."""


class MoveValidationError(Exception):
    """Raised when a rendered module fails to parse post-transform."""

    def __init__(self, text: str, cause: BaseException) -> None:
        super().__init__(f"Rendered module failed to parse: {cause}")
        self.text = text


class SharedHelpersError(Exception):
    """Raised in ``error`` mode when shared helpers would be duplicated."""

    def __init__(self, shared_helpers: list[str]) -> None:
        self.shared_helpers = list(shared_helpers)
        joined = ", ".join(self.shared_helpers)
        super().__init__(
            f"Shared helpers detected (also used by remaining symbols): {joined}"
        )


@dataclass
class SharedHelperDetection:
    """Classification record for a helper flagged as shared."""

    name: str
    used_by_moved: list[str]
    used_by_remaining: list[str]


@dataclass
class MovePlan:
    """Result of a :func:`move_symbols` call.

    Carries the rendered source and target texts, the names that were
    actually moved, and the direct dependencies (imports, constants)
    copied into the target. ``warnings`` aggregates non-fatal issues
    such as ruff post-processing errors.
    """

    source_text_new: str
    target_text_new: str
    moved_names: list[str]
    imports_added: list[str] = field(default_factory=list)
    constants_added: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    shared_helpers_detected: list[SharedHelperDetection] = field(default_factory=list)
    callers_updated: list[CallerRewrite] = field(default_factory=list)
