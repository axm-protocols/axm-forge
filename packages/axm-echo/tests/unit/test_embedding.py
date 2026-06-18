"""Unit tests for axm_echo.embedding."""

from __future__ import annotations

import sys

import numpy as np
import pytest

from axm_echo.embedding import code_tokens, embed, neighbors


def test_tfidf_backend_no_torch() -> None:
    """AC2: the tfidf backend must never import torch (lazy st-only)."""
    sys.modules.pop("torch", None)
    texts = [
        "raise RateLimitError when the api quota is exceeded",
        "compute the cosine similarity between two vectors",
        "open a file and read its bytes into memory",
    ]

    matrix = embed(texts, backend="tfidf")

    assert matrix.shape[0] == len(texts)
    assert "torch" not in sys.modules


def test_embed_unknown_backend_raises() -> None:
    """An unregistered backend name raises ValueError listing valid ones."""
    with pytest.raises(ValueError, match="unknown backend") as exc:
        embed(["x"], backend="nope")

    # The error enumerates the registered backends to guide the caller.
    assert "tfidf" in str(exc.value)


def test_code_tokens_splits_camel_and_snake_case() -> None:
    """Identifiers split into sub-tokens; structural keywords are weighted."""
    tokens = code_tokens("def readCsvRows(file_path):\n    return file_path")

    # camelCase + snake_case both decompose into lowercase sub-tokens.
    assert "read" in tokens
    assert "csv" in tokens
    assert "rows" in tokens
    assert "file" in tokens
    assert "path" in tokens
    # The 'return' structural keyword is appended once per occurrence.
    assert tokens.count("return") >= 1


def test_neighbors_threshold_drops_low_scores() -> None:
    """A cosine threshold truncates the result below the cutoff."""
    matrix = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
        dtype=np.float64,
    )
    query = np.array([1.0, 0.0, 0.0], dtype=np.float64)

    results = neighbors(query, matrix, k=10, threshold=0.5)

    # Only the identical row (cosine 1.0) clears the 0.5 threshold.
    assert len(results) == 1
    assert results[0][0] == 0


def test_neighbors_topk_cosine() -> None:
    """AC1: neighbors returns cosine top-k in decreasing order."""
    matrix = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.9, 0.1, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    query = np.array([1.0, 0.0, 0.0], dtype=np.float64)

    results = neighbors(query, matrix, k=2)

    assert len(results) == 2
    idxs = [idx for idx, _score in results]
    scores = [score for _idx, score in results]
    # The two closest rows to the query are row 0 (identical) then row 1.
    assert idxs == [0, 1]
    # Scores are cosine similarities, sorted in decreasing order.
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == pytest.approx(1.0)
