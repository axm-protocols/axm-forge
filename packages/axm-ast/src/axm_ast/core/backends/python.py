"""Python language backend.

The Python grammar logic (tree-sitter-python, the ``_extract_*`` node mappers,
the parse cache) lives in :mod:`axm_ast.core.parser` and is battle-tested by the
existing suite. This backend is a thin adapter over those functions so the
multi-language dispatch goes through one uniform interface without moving — and
risking — the proven Python extraction code. New languages implement the same
interface from scratch in their own module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from axm_ast.core import parser as _py_parser

if TYPE_CHECKING:
    from pathlib import Path

    from tree_sitter import Tree

    from axm_ast.models.nodes import ModuleInfo

__all__ = ["PythonBackend"]


class PythonBackend:
    """Adapter exposing the existing Python parser through the backend interface.

    Implements :class:`axm_ast.core.backends.base.LanguageBackend` structurally.
    """

    @property
    def name(self) -> str:
        """Language name."""
        return "python"

    @property
    def suffixes(self) -> tuple[str, ...]:
        """Python source extension."""
        return (".py",)

    def parse_source(self, source: str) -> Tree:
        """Parse Python *source* via the existing tree-sitter parser."""
        return _py_parser.parse_source(source)

    def parse_file(self, path: Path) -> Tree:
        """Parse a Python file via the existing cached parser."""
        return _py_parser.parse_file(path)

    def extract_module(self, path: Path) -> ModuleInfo:
        """Extract module info via the existing Python extractor."""
        return _py_parser.extract_module_info(path)
