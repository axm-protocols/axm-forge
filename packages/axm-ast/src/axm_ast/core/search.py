"""Shared TypedDict shapes for search tool result entries.

These types describe serialized symbol dicts and suggestion dicts produced
by ``ast_search``, lifted out of ``tools/search.py`` so that ``tools/
search_text.py`` can consume them without an explicit ``Any``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from axm_ast.models import SymbolKind

__all__ = [
    "SearchFilters",
    "SearchResultEntry",
    "Suggestion",
]


class SearchResultEntry(TypedDict, total=False):
    """Serialized symbol dict produced by ``SearchTool._format_symbol``.

    ``name`` and ``module`` are always present; the remaining keys are
    populated based on the symbol kind.
    """

    name: str
    module: str
    signature: str | None
    return_type: str | None
    kind: str
    annotation: str
    value_repr: str


class Suggestion(TypedDict):
    """Fuzzy-match suggestion for an unknown symbol query."""

    name: str
    score: float
    kind: str
    module: str


class SearchFilters(TypedDict):
    """Filter snapshot passed to text renderers."""

    name: str | None
    returns: str | None
    kind: SymbolKind | None
    inherits: str | None
