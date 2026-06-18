"""Embedding backends + brute-force cosine neighbor search.

Two registered backends, ported from the dedup-detection POC
(``find_duplicates_v7.py`` + ``trials/trial_unified.py``):

- ``tfidf``  : TF-IDF over code tokens (scikit-learn). Pure CPU, no torch.
- ``st``     : sentence-transformers MiniLM (``all-MiniLM-L6-v2``).

``torch`` / ``sentence_transformers`` are imported **lazily**, inside the
``st`` backend only, so the ``tfidf`` path never pulls torch into the
process (the base install ships without the ``neural`` extra).

Neighbor search is an **exact brute-force matmul** (no ANN): under ~10^5
vectors a single normalized dot product beats an approximate index by
7-30x while staying exact. This calibration is closed (see ticket
technical notes) and is not re-litigated here.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from numpy.typing import NDArray

__all__ = ["Backend", "code_tokens", "embed", "neighbors"]

type Backend = Literal["tfidf", "st"]

# MiniLM, not e5/bge (closed decision: discriminates 5x better, 2x faster).
_ST_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_STRUCTURAL_KEYWORDS = (
    "for",
    "while",
    "if",
    "elif",
    "else",
    "try",
    "except",
    "finally",
    "with",
    "return",
    "yield",
    "raise",
    "lambda",
    "async",
    "await",
)


def code_tokens(src: str) -> list[str]:
    """Tokenize code text for the TF-IDF backend.

    Lowercases identifiers, splits ``camelCase`` and ``snake_case`` into
    sub-tokens, and appends structural keyword hints weighted by frequency
    so control-flow shape contributes to the vector.
    """
    tokens: list[str] = []
    for ident in _IDENT_RE.findall(src):
        tokens.append(ident.lower())
        parts = re.split(r"(?<=[a-z])(?=[A-Z])|_", ident)
        tokens.extend(p.lower() for p in parts if p)
    for kw in _STRUCTURAL_KEYWORDS:
        tokens.extend([kw] * src.count(kw))
    return tokens


def _embed_tfidf(texts: Sequence[str]) -> NDArray[np.float64]:
    """TF-IDF code embedding (scikit-learn). Never imports torch."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    vec = TfidfVectorizer(
        tokenizer=code_tokens,
        lowercase=False,
        min_df=1,
        sublinear_tf=True,
        token_pattern=None,
    )
    matrix = vec.fit_transform(list(texts))
    return np.asarray(matrix.todense(), dtype=np.float64)


def _embed_st(texts: Sequence[str]) -> NDArray[np.float64]:  # pragma: no cover
    """MiniLM sentence-transformer embedding.

    ``torch`` and ``sentence_transformers`` are imported here, inside the
    function, so the ``tfidf`` path never loads them (AC2).

    Coverage-exempt: this path requires the optional ``neural`` extra
    (torch + sentence-transformers, ~1-2 GB). Installing it in CI would
    defeat the very install-isolation invariant the package guarantees, so
    it is exercised only when the extra is present (the ``st`` integration
    test ``importorskip``s it) and excluded from the coverage gate.
    """
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(_ST_MODEL)
    try:
        import torch

        if torch.backends.mps.is_available():
            model = model.to("mps")
    except Exception:  # noqa: BLE001, S110 - device placement is best-effort
        pass
    embeddings = model.encode(
        list(texts),
        batch_size=128,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return np.asarray(embeddings, dtype=np.float64)


_BACKENDS: dict[Backend, Callable[[Sequence[str]], NDArray[np.float64]]] = {
    "tfidf": _embed_tfidf,
    "st": _embed_st,
}


def embed(texts: Sequence[str], *, backend: Backend = "tfidf") -> NDArray[np.float64]:
    """Embed ``texts`` into a dense matrix via the chosen backend.

    Args:
        texts: Texts to embed (one row per text).
        backend: ``"tfidf"`` (code, scikit-learn) or ``"st"`` (MiniLM).
            The ``st`` backend lazily imports torch; ``tfidf`` never does.

    Returns:
        A ``(len(texts), dim)`` float matrix. Rows are not guaranteed
        normalized; ``neighbors`` normalizes internally.

    Raises:
        ValueError: If ``backend`` is not a registered backend.
    """
    try:
        fn = _BACKENDS[backend]
    except KeyError:
        valid = ", ".join(sorted(_BACKENDS))
        msg = f"unknown backend {backend!r}; expected one of: {valid}"
        raise ValueError(msg) from None
    return fn(texts)


def _l2_normalize(matrix: NDArray[np.float64]) -> NDArray[np.float64]:
    norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return np.asarray(matrix / norms, dtype=np.float64)


def neighbors(
    query: NDArray[np.float64],
    matrix: NDArray[np.float64],
    *,
    k: int = 10,
    threshold: float | None = None,
) -> list[tuple[int, float]]:
    """Cosine top-k nearest rows to ``query`` (exact brute-force matmul).

    Args:
        query: A single query vector of shape ``(dim,)``.
        matrix: Corpus matrix of shape ``(n, dim)``.
        k: Maximum number of neighbors to return.
        threshold: If set, drop neighbors with cosine below this value.

    Returns:
        A list of ``(row_index, cosine_score)`` pairs sorted by score
        descending, length ``<= k``. The query is not excluded from the
        corpus; if ``query`` is a row of ``matrix`` it appears at score 1.0.
    """
    norm_matrix = _l2_normalize(np.atleast_2d(matrix).astype(np.float64))
    norm_query = _l2_normalize(np.asarray(query, dtype=np.float64).reshape(1, -1))
    sims = (norm_query @ norm_matrix.T).ravel()

    order = np.argsort(-sims)
    results: list[tuple[int, float]] = []
    for idx in order:
        score = float(sims[idx])
        if threshold is not None and score < threshold:
            break
        results.append((int(idx), score))
        if len(results) >= k:
            break
    return results
