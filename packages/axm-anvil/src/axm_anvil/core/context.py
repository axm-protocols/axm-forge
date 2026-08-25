"""Grouped parameter bundle for the parameter-heavy move helpers.

The move pipeline threads the same cluster of plan-assembly values
(rendered texts, moved names, added imports/constants, shared-helper map and
the caller/redundant-import warning lists) through its helpers. Collecting
them into a single frozen :class:`MoveContext` lets those signatures drop the
``# noqa: PLR0913`` waiver they previously carried while keeping the public
:func:`~axm_anvil.core.move.move_symbols` entrypoint unchanged (the context is
built internally).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from axm_anvil.core.callers import CallerRewrite
    from axm_anvil.core.shared import SharedInfo

__all__ = ["MoveContext"]


@dataclass(frozen=True)
class MoveContext:
    """Immutable bundle of the recurring move-plan assembly parameters.

    Groups the values previously passed positionally to the parameter-heavy
    move helpers (e.g. ``_build_plan``): the rendered ``source``/``target``
    texts, the names actually moved, the imports and constants copied into the
    target, the shared-helper usage map, and the optional caller-rewrite /
    redundant-import warning payloads.
    """

    source_text_new: str
    target_text_new: str
    moved_names: list[str]
    imports_added: list[str]
    constants_added: list[str]
    shared_map: dict[str, SharedInfo]
    callers_updated: list[CallerRewrite] | None = None
    redundant_import_warnings: list[str] | None = None
