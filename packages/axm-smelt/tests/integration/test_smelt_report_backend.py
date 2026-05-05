from __future__ import annotations

import json
import logging

import pytest

from axm_smelt import CounterBackend
from axm_smelt.core import counter as counter_mod
from axm_smelt.core.counter import count_with_backend
from axm_smelt.core.pipeline import smelt

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _reset_warn() -> None:
    counter_mod._warned = False


def test_smelt_report_backend_tiktoken(caplog: pytest.LogCaptureFixture) -> None:
    text = json.dumps({"a": 1, "b": [1, 2, 3], "c": "hello world"})
    with caplog.at_level(logging.WARNING):
        report = smelt(text)
    assert report.counter_backend is CounterBackend.TIKTOKEN
    assert not [r for r in caplog.records if "tiktoken unavailable" in r.message]


def test_smelt_report_backend_fallback_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = json.dumps({"a": 1, "b": [1, 2, 3], "c": "hello world"})

    calls = {"n": 0}

    def fake(t: str, model: str = "o200k_base") -> tuple[int, CounterBackend]:
        calls["n"] += 1
        if calls["n"] == 2:
            return (len(t) // 4, CounterBackend.FALLBACK)
        n, _ = count_with_backend(t, model)
        return (n, CounterBackend.TIKTOKEN)

    monkeypatch.setattr("axm_smelt.core.pipeline.count_with_backend", fake)
    report = smelt(text)
    assert report.counter_backend is CounterBackend.FALLBACK
