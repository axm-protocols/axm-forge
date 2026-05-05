from __future__ import annotations

import logging

import pytest

from axm_smelt import CounterBackend
from axm_smelt.core import counter as counter_mod
from axm_smelt.core.counter import count, count_with_backend


@pytest.fixture(autouse=True)
def _reset_warn() -> None:
    counter_mod._warned = False


def test_counter_backend_enum() -> None:
    assert CounterBackend.TIKTOKEN
    assert CounterBackend.FALLBACK


def test_count_with_backend_tiktoken_path() -> None:
    n, backend = count_with_backend("hello world")
    assert isinstance(n, int)
    assert n > 0
    assert backend is CounterBackend.TIKTOKEN


def test_count_with_backend_fallback_path(monkeypatch: pytest.MonkeyPatch) -> None:
    import tiktoken

    def _raise(*_a: object, **_k: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(tiktoken, "get_encoding", _raise)
    text = "hello world"
    n, backend = count_with_backend(text)
    assert backend is CounterBackend.FALLBACK
    assert n == len(text) // 4


def test_warn_emitted_once(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import tiktoken

    def _raise(*_a: object, **_k: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(tiktoken, "get_encoding", _raise)
    counter_mod._warned = False
    with caplog.at_level(logging.WARNING):
        for _ in range(5):
            count_with_backend("xxxx")
    matching = [r for r in caplog.records if "tiktoken unavailable" in r.message]
    assert len(matching) == 1
    assert matching[0].levelno == logging.WARNING


def test_count_int_signature_unchanged() -> None:
    result = count("hello")
    assert isinstance(result, int)
    assert not isinstance(result, tuple)
