"""Integration: accented parsed= input is not token-inflated by escaping."""

from __future__ import annotations

import json

import pytest

from axm_smelt.core.counter import count
from axm_smelt.core.pipeline import check, resolve_input, smelt

pytestmark = pytest.mark.integration


def test_accented_parsed_input_no_token_inflation() -> None:
    """AC3: the UTF-8 working text never costs more tokens than the escaped form.

    The escaped serialization (``ensure_ascii=True``) turns every accented
    character into a 6-char ``\\uXXXX`` sequence, inflating the token count.
    Serializing as raw UTF-8 keeps the count at or below that form while the
    accented characters survive verbatim.
    """
    parsed = {
        "ville": "Genève",
        "resume": "café crème, déjà vu, naïveté, cœur",
        "auteur": "Frédéric",
    }
    escaped = json.dumps(parsed, separators=(",", ":"))

    working, _ = resolve_input(text=None, parsed=parsed)

    assert "\\u" not in working
    assert "Genève" in working
    assert count(working) <= count(escaped)


def test_accented_parsed_through_non_minify_preset() -> None:
    """AC2/AC3: raw UTF-8 survives the parsed= path with a non-minify strategy."""
    parsed = {"ville": "Genève", "note": "café crème"}
    escaped = json.dumps(parsed, separators=(",", ":"))

    report = smelt(parsed=parsed, strategies=["tabular"])
    check_report = check(parsed=parsed)

    assert "\\u" not in report.original
    assert "Genève" in report.original
    assert "\\u" not in check_report.compacted
    assert report.original_tokens <= count(escaped)
