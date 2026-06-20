"""Per-language backend interface for multi-language AST analysis.

axm-ast analyses *files*, so the dimension that varies is the **file's
language**, detected from its extension — not the project framework (that is
audit's concern, and it auto-detects too; only init takes an explicit
framework). A :class:`LanguageBackend` isolates everything language-specific:
the tree-sitter grammar, the node-name mapping into the shared symbol model,
the import semantics, and the call-extraction node names.

The shared machinery downstream (call-graph, impact, dead-code, the ``ast_*``
tools, formatters) consumes only the language-agnostic ``ModuleInfo`` /
``CallSite`` models and never sees the language again.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path

    from tree_sitter import Tree

    from axm_ast.models.nodes import ModuleInfo

__all__ = ["LanguageBackend"]


@runtime_checkable
class LanguageBackend(Protocol):
    """A language-specific parsing + symbol-extraction backend.

    Implementations live in ``core/backends/<language>.py`` and register
    themselves in ``core/registry.py`` keyed by file suffix. The four members
    map exactly to the four points where the language matters:

    * :attr:`suffixes` — which file extensions this backend owns.
    * :meth:`parse_source` — grammar (tree-sitter ``Language``/``Parser``).
    * :meth:`extract_module` — node-name mapping into :class:`ModuleInfo`.
    * (import resolution and call extraction are handled by the analyzer/
      callers layers, which dispatch to the backend that owns each file.)

    Everything else — ranking, impact, dead-code, traversal, the MCP tools —
    is language-agnostic and consumes the returned :class:`ModuleInfo`.
    """

    @property
    def name(self) -> str:
        """Human-readable language name (e.g. ``"python"``, ``"typescript"``)."""
        ...

    @property
    def suffixes(self) -> tuple[str, ...]:
        """File extensions this backend owns (e.g. ``(".py",)``)."""
        ...

    def parse_source(self, source: str) -> Tree:
        """Parse *source* into a tree-sitter ``Tree`` with this grammar."""
        ...

    def parse_file(self, path: Path) -> Tree:
        """Parse the file at *path* into a tree-sitter ``Tree``.

        Implementations may cache by (path, mtime); they must raise
        ``FileNotFoundError`` for a missing file.
        """
        ...

    def extract_module(self, path: Path) -> ModuleInfo:
        """Extract the full :class:`ModuleInfo` (symbols, imports, docstring).

        This is the only language-aware step: it walks the grammar's concrete
        syntax tree, mapping language-specific node types into the shared,
        language-agnostic symbol model.
        """
        ...
