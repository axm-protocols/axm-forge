"""Language-dispatching parse/extract entry points.

The public ``parse_file`` / ``extract_module_info`` in :mod:`axm_ast.core.parser`
are the Python implementation (and the body of :class:`PythonBackend`). This
module is the *multi-language* layer above them: it routes a path to the backend
that owns its suffix, so callers that may see ``.py`` **or** ``.ts`` files use
one entry point and never branch on language themselves.

For ``.py`` files this is byte-identical to calling ``parser`` directly (the
registry returns the Python backend, which delegates to ``parser``), so existing
Python-only call paths are unaffected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from axm_ast.core.backends import backend_for

if TYPE_CHECKING:
    from pathlib import Path

    from tree_sitter import Tree

    from axm_ast.models.nodes import ModuleInfo

__all__ = ["extract_module", "parse_path"]


def parse_path(path: Path) -> Tree:
    """Parse *path* with the backend that owns its suffix.

    Args:
        path: Source file in any supported language (``.py``, ``.ts``, …).

    Returns:
        The parsed tree-sitter ``Tree``.

    Raises:
        ValueError: If no backend is registered for the file's suffix.
        FileNotFoundError: If the file does not exist.
    """
    backend = backend_for(path)
    if backend is None:
        msg = f"Unsupported file type for AST parsing: {path}"
        raise ValueError(msg)
    return backend.parse_file(path)


def extract_module(path: Path) -> ModuleInfo:
    """Extract :class:`ModuleInfo` from *path* via its language backend.

    Args:
        path: Source file in any supported language.

    Returns:
        The language-agnostic :class:`ModuleInfo` for the file.

    Raises:
        ValueError: If no backend is registered for the file's suffix.
        FileNotFoundError: If the file does not exist.
    """
    backend = backend_for(path)
    if backend is None:
        msg = f"Unsupported file type for AST extraction: {path}"
        raise ValueError(msg)
    return backend.extract_module(path)
