"""Abstract base for compaction strategies."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from axm_smelt.core.models import SmeltContext

__all__ = ["SmeltStrategy"]


class SmeltStrategy(abc.ABC):
    """Base class for all compaction strategies."""

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    @abc.abstractmethod
    def category(self) -> str: ...

    @abc.abstractmethod
    def apply(self, ctx: SmeltContext) -> SmeltContext:
        """Apply the compaction strategy to the given context.

        Receives a ``SmeltContext`` carrying the current text (and optional
        parsed representation) and returns a new ``SmeltContext`` with the
        compacted result.  If the strategy does not apply, return *ctx*
        unchanged.
        """
        ...
