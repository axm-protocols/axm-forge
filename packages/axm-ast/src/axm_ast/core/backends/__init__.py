"""Per-language AST backends and their suffix-keyed registry.

``LanguageBackend`` is the interface; ``registry`` dispatches a file to its
backend by extension. Python is built in; TypeScript/Svelte are optional.
"""

from __future__ import annotations

from axm_ast.core.backends.base import LanguageBackend
from axm_ast.core.backends.registry import (
    backend_for,
    get_backend,
    register_backend,
    supported_suffixes,
)

__all__ = [
    "LanguageBackend",
    "backend_for",
    "get_backend",
    "register_backend",
    "supported_suffixes",
]
