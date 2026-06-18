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
from axm_echo.structural import (
    flatten_body,
    jaccard_similarity,
    normalize_dump,
    statement_set,
)
from axm_echo.tools import EchoCodeTool

__all__ = [
    "Backend",
    "EchoCodeTool",
    "Symbol",
    "SymbolDict",
    "code_tokens",
    "config_path",
    "discover_package_roots",
    "embed",
    "extract_monorepo",
    "extract_package",
    "flatten_body",
    "jaccard_similarity",
    "load_scope",
    "neighbors",
    "normalize_dump",
    "statement_set",
]
