"""Shared AST helpers for rule implementations."""

from __future__ import annotations

import ast
import logging
import threading
from contextvars import ContextVar, Token
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = [
    "ASTCache",
    "get_active_cache",
    "get_ast_cache",
    "get_python_files",
    "parse_file_safe",
    "reset_ast_cache",
    "set_ast_cache",
]


def get_python_files(directory: Path) -> list[Path]:
    """Get all Python files in a directory recursively."""
    if not directory.exists():
        return []
    return list(directory.rglob("*.py"))


def parse_file_safe(path: Path) -> ast.Module | None:
    """Parse a Python file, returning None on error."""
    try:
        return ast.parse(path.read_text(), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return None


# ── AST Cache ─────────────────────────────────────────────────────────


class ASTCache:
    """Thread-safe AST parse cache.

    Parses each file at most once per audit session.  Uses
    double-checked locking so multiple threads hitting the same
    file don't duplicate work.
    """

    def __init__(self) -> None:
        self._cache: dict[Path, ast.Module | None] = {}
        self._lock = threading.Lock()

    def get_or_parse(self, path: Path) -> ast.Module | None:
        """Return cached AST or parse *path* and cache the result."""
        resolved = path.resolve()
        if resolved in self._cache:
            return self._cache[resolved]
        with self._lock:
            # Double-check after acquiring lock
            if resolved not in self._cache:
                self._cache[resolved] = parse_file_safe(resolved)
        return self._cache[resolved]


# ── Module-level cache accessor ──────────────────────────────────────

_ACTIVE_CACHE: ContextVar[ASTCache | None] = ContextVar("axm_audit_ast_cache")

_broadcast_cache: ASTCache | None = None


def set_ast_cache(cache: ASTCache | None) -> Token[ASTCache | None]:
    """Bind *cache* to the current context and return the reset token."""
    global _broadcast_cache
    _broadcast_cache = cache
    return _ACTIVE_CACHE.set(cache)


def reset_ast_cache(token: Token[ASTCache | None]) -> None:
    """Reset the active cache using a token from :func:`set_ast_cache`."""
    global _broadcast_cache
    _ACTIVE_CACHE.reset(token)
    _broadcast_cache = None


def get_ast_cache() -> ASTCache | None:
    """Return the active ``ASTCache``, or ``None`` outside audits."""
    try:
        return _ACTIVE_CACHE.get()
    except LookupError:
        return _broadcast_cache


get_active_cache = get_ast_cache
