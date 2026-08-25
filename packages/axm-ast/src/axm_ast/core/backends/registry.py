"""Language-backend registry — auto-detects a file's backend by extension.

The registry is the single dispatch point: ``backend_for(path)`` returns the
:class:`LanguageBackend` that owns the file's suffix, or ``None`` for an
unsupported extension. ``supported_suffixes()`` powers file discovery so the
analyzer collects every language's files, not just ``.py``.

The Python backend is always registered. Optional backends (TypeScript, Svelte)
register themselves on first import *iff* their optional tree-sitter grammar is
installed (``axm-ast[typescript]``), mirroring axm-echo's lazy-torch convention.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from axm_ast.core.backends.base import LanguageBackend

__all__ = [
    "backend_for",
    "get_backend",
    "register_backend",
    "supported_suffixes",
]

_REGISTRY: dict[str, LanguageBackend] = {}
# Guards lazy default-backend registration: the audit runner analyses rules in
# a ThreadPoolExecutor, so first-time init can be hit concurrently. Without the
# lock a racing thread could observe the "loaded" flag before the registry was
# actually populated and see an empty registry.
_init_lock = threading.Lock()


def register_backend(backend: LanguageBackend) -> None:
    """Register *backend* for each of its suffixes (idempotent, last wins)."""
    for suffix in backend.suffixes:
        _REGISTRY[suffix] = backend


def get_backend(suffix: str) -> LanguageBackend | None:
    """Return the backend registered for *suffix*, or ``None`` if unsupported."""
    _ensure_default_backends()
    return _REGISTRY.get(suffix)


def backend_for(path: Path) -> LanguageBackend | None:
    """Return the backend that owns *path* by its suffix, or ``None``."""
    return get_backend(path.suffix)


def supported_suffixes() -> frozenset[str]:
    """Return every registered file suffix (used for multi-language discovery)."""
    _ensure_default_backends()
    return frozenset(_REGISTRY)


_defaults_loaded = False


def _ensure_default_backends() -> None:
    """Lazily import and register the built-in backends, once.

    Python is mandatory. TypeScript is optional: its import is attempted and
    silently skipped if ``tree-sitter-typescript`` is not installed, so a
    Python-only install of axm-ast never pays for the TS grammar.
    """
    global _defaults_loaded
    if _defaults_loaded:
        return
    with _init_lock:
        # Re-check under the lock: another thread may have finished init while
        # this one waited.
        if _defaults_loaded:
            return

        from axm_ast.core.backends.python import PythonBackend

        register_backend(PythonBackend())

        try:
            from axm_ast.core.backends.typescript import TypeScriptBackend
        except ImportError:
            # Optional grammar not installed — TS files are simply unsupported.
            pass
        else:
            register_backend(TypeScriptBackend())

        # Set the flag only AFTER the registry is fully populated, so a racing
        # reader never sees "loaded" with an empty registry.
        _defaults_loaded = True
