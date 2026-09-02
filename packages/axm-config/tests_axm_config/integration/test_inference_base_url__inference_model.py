"""Integration coverage for unconfigured inference defaults."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_config import paths


@pytest.mark.integration
def test_inference_base_url_returns_documented_default_when_unconfigured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: an empty configuration yields the documented engine address."""
    monkeypatch.setenv("AXM_HOME", str(tmp_path))
    monkeypatch.delenv("AXM_INFERENCE_BASE_URL", raising=False)

    assert paths.inference_base_url() == "http://127.0.0.1:8000/v1"


@pytest.mark.integration
def test_inference_model_returns_documented_default_when_unconfigured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: an empty configuration yields the documented model identifier."""
    monkeypatch.setenv("AXM_HOME", str(tmp_path))
    monkeypatch.delenv("AXM_INFERENCE_MODEL", raising=False)

    assert paths.inference_model() == "ornith-ai/Ornith-1.5-9B-MLX-4bit"
