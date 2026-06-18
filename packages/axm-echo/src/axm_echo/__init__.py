"""axm-echo.

Similarity & echo detection over code corpora (numpy/scikit-learn).
"""

from __future__ import annotations

from axm_echo.corpus import (
    Symbol,
    SymbolDict,
    discover_package_roots,
    extract_monorepo,
    extract_package,
)
from axm_echo.embedding import Backend, code_tokens, embed, neighbors
from axm_echo.scope import config_path, load_scope

__all__ = [
    "Backend",
    "Symbol",
    "SymbolDict",
    "code_tokens",
    "config_path",
    "discover_package_roots",
    "embed",
    "extract_monorepo",
    "extract_package",
    "load_scope",
    "neighbors",
]
