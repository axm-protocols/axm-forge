from __future__ import annotations

import json
import logging

import pytest
import tiktoken
from pytest_mock import MockerFixture

from axm_smelt import CounterBackend
from axm_smelt.core import counter
from axm_smelt.core.counter import count, count_with_backend
from axm_smelt.core.pipeline import smelt

# --- count() ---


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("hello world", id="ascii_basic"),
        pytest.param("   \n\t  ", id="whitespace_only"),
        pytest.param("éèê \U0001f600\U0001f4a1", id="unicode_with_emoji"),
    ],
)
def test_count_returns_positive_int(text: str) -> None:
    """Non-empty text returns a positive integer token count."""
    result = count(text)
    assert isinstance(result, int)
    assert result > 0


def test_count_empty() -> None:
    result = count("")
    assert isinstance(result, int)
    assert result >= 0


def test_count_model_parameter() -> None:
    """AC6: encoding names (o200k_base, cl100k_base) and an OpenAI model name
    each return valid counts; encoding names keep resolving (no regression)."""
    text = "The quick brown fox jumps over the lazy dog."
    for model in ("o200k_base", "cl100k_base", "gpt-4o"):
        result = count(text, model=model)
        assert isinstance(result, int)
        assert result > 0


def test_count_resolves_openai_model_names() -> None:
    """AC6: OpenAI model names resolve via tiktoken (not fallback) and match
    the count from tiktoken.encoding_for_model."""
    text = "The quick brown fox jumps over the lazy dog."
    for model in ("gpt-4o", "gpt-4"):
        n, backend = count_with_backend(text, model)
        assert backend is CounterBackend.TIKTOKEN
        expected = len(tiktoken.encoding_for_model(model).encode(text))
        assert n == expected


def test_count_int_signature_unchanged() -> None:
    result = count("hello")
    assert isinstance(result, int)
    assert not isinstance(result, tuple)


# --- Claude proxy + unknown-model routing ---


def test_claude_model_routes_to_o200k() -> None:
    """AC5, AC6: a Claude model name is counted by tiktoken via the o200k_base
    proxy encoding (backend TIKTOKEN), never len//4."""
    n, backend = count_with_backend("hello world", model="claude-opus-4-8")
    assert n > 0
    assert backend is CounterBackend.TIKTOKEN
    # Proxy is o200k_base: count matches that encoding exactly.
    expected = len(tiktoken.get_encoding("o200k_base").encode("hello world"))
    assert n == expected


def test_claude_model_case_insensitive() -> None:
    """AC5: the claude prefix is matched case-insensitively."""
    n, backend = count_with_backend("hello world", model="Claude-Sonnet-4-5")
    assert backend is CounterBackend.TIKTOKEN
    assert n > 0


def test_unknown_model_routes_to_o200k() -> None:
    """AC2: a genuinely unknown model name routes to o200k_base (backend
    TIKTOKEN), never len//4."""
    n, backend = count_with_backend("hello", model="some-unknown-model")
    assert backend is CounterBackend.TIKTOKEN
    assert n > 0


def test_openai_model_still_exact() -> None:
    """AC6: an OpenAI model keeps resolving to its exact tiktoken encoding."""
    n, backend = count_with_backend("hello", model="gpt-4o")
    assert backend is CounterBackend.TIKTOKEN
    assert n > 0


# --- encoding cache ---


def test_count_caches_encoding_once(mocker: MockerFixture) -> None:
    counter._ENC.clear()
    spy = mocker.spy(tiktoken, "get_encoding")
    for _ in range(100):
        counter.count("hello", model="o200k_base")
    assert spy.call_count == 1


def test_count_caches_per_model(mocker: MockerFixture) -> None:
    """Each distinct key resolves once; the cache holds both an encoding name
    and a model name independently."""
    counter._ENC.clear()
    enc_spy = mocker.spy(tiktoken, "get_encoding")
    model_spy = mocker.spy(tiktoken, "encoding_for_model")
    for _ in range(5):
        counter.count("x", model="o200k_base")
    for _ in range(5):
        counter.count("x", model="gpt-4o")
    # gpt-4o resolves via encoding_for_model; o200k_base falls through to
    # get_encoding after encoding_for_model raises KeyError -> 2 model-name
    # attempts, 1 raw-encoding attempt. No re-resolution on cache hits.
    assert model_spy.call_count == 2
    assert enc_spy.call_count == 1
    assert "o200k_base" in counter._ENC
    assert "gpt-4o" in counter._ENC


# --- CounterBackend enum (no FALLBACK) ---


def test_counter_backend_has_no_fallback() -> None:
    """AC3: CounterBackend has only TIKTOKEN; FALLBACK is removed."""
    assert CounterBackend.TIKTOKEN
    assert not hasattr(CounterBackend, "FALLBACK")


def test_reset_warned_removed() -> None:
    """AC4: the one-shot warning seam (_warned / reset_warned) is removed."""
    assert not hasattr(counter, "reset_warned")
    assert not hasattr(counter, "_warned")


def test_count_with_backend_tiktoken_path() -> None:
    """AC6: the nominal path returns a positive count via the TIKTOKEN backend."""
    n, backend = count_with_backend("hello world")
    assert isinstance(n, int)
    assert n > 0
    assert backend is CounterBackend.TIKTOKEN


# --- SmeltReport backend column ---


def test_smelt_report_backend_tiktoken(caplog: pytest.LogCaptureFixture) -> None:
    """AC7: SmeltReport.counter_backend is populated and is TIKTOKEN."""
    text = json.dumps({"a": 1, "b": [1, 2, 3], "c": "hello world"})
    with caplog.at_level(logging.WARNING):
        report = smelt(text)
    assert report.counter_backend is CounterBackend.TIKTOKEN
    assert not [r for r in caplog.records if "tiktoken unavailable" in r.message]
