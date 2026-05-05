from __future__ import annotations

from typing import Any

import pytest
import tiktoken
from pytest_mock import MockerFixture

from axm_smelt.core import counter
from axm_smelt.core.counter import count


def test_count_basic() -> None:
    result = count("hello world")
    assert isinstance(result, int)
    assert result > 0


def test_count_empty() -> None:
    result = count("")
    assert isinstance(result, int)
    assert result >= 0


def test_count_whitespace_only() -> None:
    """Whitespace string returns token count > 0."""
    result = count("   \n\t  ")
    assert isinstance(result, int)
    assert result > 0


def test_count_unicode() -> None:
    """Unicode/emoji text returns valid token count."""
    result = count("éèê \U0001f600\U0001f4a1")
    assert isinstance(result, int)
    assert result > 0


def test_count_model_parameter() -> None:
    """Different model encodings each return valid counts."""
    text = "The quick brown fox jumps over the lazy dog."
    for model in ("o200k_base", "cl100k_base"):
        result = count(text, model=model)
        assert isinstance(result, int)
        assert result > 0


def test_count_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """When tiktoken raises, falls back to len // 4."""
    counter._ENC.clear()

    def _raise(model: str) -> Any:
        raise RuntimeError("mocked")

    monkeypatch.setattr(tiktoken, "get_encoding", _raise)
    result = count("abcdefghijklmnop")  # 16 chars -> 4
    assert result == 4


def test_count_caches_encoding_once(mocker: MockerFixture) -> None:
    counter._ENC.clear()
    spy = mocker.spy(tiktoken, "get_encoding")
    for _ in range(100):
        counter.count("hello", model="o200k_base")
    assert spy.call_count == 1


def test_count_caches_per_model(mocker: MockerFixture) -> None:
    counter._ENC.clear()
    spy = mocker.spy(tiktoken, "get_encoding")
    for _ in range(5):
        counter.count("x", model="o200k_base")
    for _ in range(5):
        counter.count("x", model="cl100k_base")
    assert spy.call_count == 2


def test_cache_not_poisoned_on_failure(mocker: MockerFixture) -> None:
    counter._ENC.clear()
    real_get_encoding = tiktoken.get_encoding
    calls = {"n": 0}

    def flaky(model: str) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return real_get_encoding(model)

    mocker.patch("axm_smelt.core.counter.tiktoken.get_encoding", side_effect=flaky)

    text = "the quick brown fox jumps over the lazy dog"
    first = counter.count(text, model="o200k_base")
    assert first == len(text) // 4
    assert "o200k_base" not in counter._ENC

    second = counter.count(text, model="o200k_base")
    assert second != len(text) // 4
    assert "o200k_base" in counter._ENC


@pytest.fixture
def _reset_warn() -> None:
    counter._warned = False


def test_counter_backend_enum() -> None:
    from axm_smelt import CounterBackend

    assert CounterBackend.TIKTOKEN
    assert CounterBackend.FALLBACK


def test_count_with_backend_tiktoken_path() -> None:
    from axm_smelt import CounterBackend
    from axm_smelt.core.counter import count_with_backend

    n, backend = count_with_backend("hello world")
    assert isinstance(n, int)
    assert n > 0
    assert backend is CounterBackend.TIKTOKEN


def test_count_with_backend_fallback_path(
    monkeypatch: pytest.MonkeyPatch, _reset_warn: None
) -> None:
    from axm_smelt import CounterBackend
    from axm_smelt.core.counter import count_with_backend

    counter._ENC.clear()

    def _raise(model: str) -> Any:
        raise RuntimeError("mocked")

    monkeypatch.setattr(tiktoken, "get_encoding", _raise)
    text = "abcdefghijklmnop"
    n, backend = count_with_backend(text)
    assert backend is CounterBackend.FALLBACK
    assert n == len(text) // 4


def test_warn_emitted_once(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    _reset_warn: None,
) -> None:
    import logging

    from axm_smelt.core.counter import count_with_backend

    counter._ENC.clear()

    def _raise(model: str) -> Any:
        raise RuntimeError("mocked")

    monkeypatch.setattr(tiktoken, "get_encoding", _raise)

    with caplog.at_level(logging.WARNING):
        for _ in range(5):
            count_with_backend("hello")

    matching = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "tiktoken unavailable" in r.getMessage()
    ]
    assert len(matching) == 1


def test_count_int_signature_unchanged() -> None:
    result = count("hello")
    assert isinstance(result, int)
    assert not isinstance(result, tuple)
