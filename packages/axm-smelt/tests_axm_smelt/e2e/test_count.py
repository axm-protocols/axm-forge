from __future__ import annotations

import subprocess

import pytest
import tiktoken

pytestmark = pytest.mark.e2e


def test_count_with_model_name() -> None:
    """AC1: `count --model gpt-4o` exits 0 and prints the o200k_base token
    count for the same input (proving no silent len // 4 divergence)."""
    text = "The quick brown fox jumps over the lazy dog."
    result = subprocess.run(
        ["uv", "run", "axm-smelt", "count", "--model", "gpt-4o"],  # noqa: S607
        capture_output=True,
        text=True,
        input=text,
    )
    assert result.returncode == 0
    expected = len(tiktoken.encoding_for_model("gpt-4o").encode(text))
    assert int(result.stdout.strip()) == expected
