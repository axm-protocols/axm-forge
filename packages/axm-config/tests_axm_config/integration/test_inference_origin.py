"""Integration coverage for inference-origin configuration fallback."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_config import paths


@pytest.mark.integration
def test_inference_origin_returns_local_when_unconfigured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: an empty configuration home preserves the documented local default."""
    monkeypatch.setenv("AXM_HOME", str(tmp_path))
    monkeypatch.delenv("AXM_INFERENCE_ORIGIN", raising=False)

    assert paths.inference_origin() == "local"
