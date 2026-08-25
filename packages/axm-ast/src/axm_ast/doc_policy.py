"""Documentation-required policy predicate for axm-ast symbols.

This module hosts the single, shared notion of *"is this symbol required to be
documented?"* consumed by the ``doc_impact`` detector. It deliberately mirrors
the axm-audit **practices** docstring-coverage rule -- the canonical spec --
``axm_audit.core.rules.practices.docstring_coverage.DocstringCoverageRule``:

* public surface only: a symbol whose name does **not** start with ``_``;
* a symbol carrying a docstring is considered documented (presence only, never
  content/quality).

Because the practices rule skips every name starting with ``_``, dunders such as
``__init__`` (which start with ``_``) are **not** treated as required public
surface -- this predicate keeps that behaviour so the two never drift apart.
When the practices rule changes, update this predicate to match it.

The docstring itself is read from the node's ``docstring`` field, which axm-ast
already populates from the tree-sitter/AST docstring node
(``axm_ast.core.parser._extract_docstring``). No bespoke "has docstring"
heuristic is introduced here.
"""

from __future__ import annotations

from axm_ast.models.nodes import ClassInfo, FunctionInfo, ModuleInfo

__all__ = ["is_documentation_required"]


def is_documentation_required(
    symbol: FunctionInfo | ClassInfo | ModuleInfo,
) -> bool:
    """Return ``True`` only for a public symbol that lacks a docstring.

    A symbol is documentation-required when it is part of the public surface
    (its name does not start with ``_`` -- which also excludes dunders such as
    ``__init__``, mirroring the axm-audit practices docstring-coverage rule)
    **and** it carries no docstring.

    Presence only: any non-empty docstring -- regardless of content or quality
    -- satisfies the policy. The docstring is taken from the node's
    ``docstring`` field, extracted upstream via axm-ast's tree-sitter docstring
    node; no divergent "has docstring" heuristic is applied here.

    Args:
        symbol: A parsed axm-ast node (function/method, class, or module).

    Returns:
        ``True`` if the symbol must be documented but is not; ``False`` when it
        is private/dunder (never required) or already carries a docstring.
    """
    name = symbol.name
    if name is None or name.startswith("_"):
        return False
    docstring = symbol.docstring
    return not (docstring is not None and docstring.strip() != "")
