"""Editorial contract of the ``axm_ast.core.doc_impact`` public docstrings.

The three signals of ``ast_doc_impact`` (doc refs, undocumented, stale
signatures) rest on a purely lexical matching. That caveat is carried by the
docstrings of the public entry points, which are the single editorial source of
truth this module locks. No I/O: the contract is read from an in-memory
attribute.
"""

from __future__ import annotations

import pytest

from axm_ast.core.doc_impact import (
    analyze_doc_impact,
    find_doc_refs,
    find_stale_signatures,
    find_undocumented,
)


def _doc(func: object) -> str:
    """Return the lowercased docstring of ``func`` (empty string if absent)."""
    return (func.__doc__ or "").lower()


@pytest.mark.parametrize(
    "func",
    [analyze_doc_impact, find_doc_refs, find_undocumented],
    ids=["analyze_doc_impact", "find_doc_refs", "find_undocumented"],
)
def test_public_entry_points_document_lexical_matching(func: object) -> None:
    """AC1: the three public entry points state the matching is lexical.

    Each docstring must name the lexical nature of the hit, the backtick form
    and the fenced-code-block form.
    """
    text = _doc(func)

    assert "lexical" in text
    assert "backtick" in text
    assert "fenc" in text


def test_analyze_doc_impact_documents_pages_to_read_and_name_drop() -> None:
    """AC2: doc refs are pages to read, not a proof; a name-drop suppresses."""
    text = _doc(analyze_doc_impact)

    assert "pages to read" in text
    assert "not a proof" in text
    assert "name-drop" in text


@pytest.mark.parametrize(
    "func",
    [analyze_doc_impact, find_doc_refs],
    ids=["analyze_doc_impact", "find_doc_refs"],
)
def test_output_forbidden_as_non_regression_oracle(func: object) -> None:
    """AC3: both docstrings forbid using the output as a non-regression oracle."""
    text = _doc(func)

    assert "oracle" in text
    assert "non-regression" in text


def test_find_stale_signatures_documents_fenced_block_scope() -> None:
    """AC4: the stale-signature scope is limited to fenced code blocks."""
    text = _doc(find_stale_signatures)

    assert "fenced code block" in text
    assert "signature" in text
