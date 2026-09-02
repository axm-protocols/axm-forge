from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import tiktoken


@pytest.mark.e2e
def test_count_with_model_name() -> None:
    """AC1: `smelt_count --model gpt-4o` exits 0 and prints the o200k_base
    token count for the same input (proving no silent len // 4 divergence)."""
    text = ""
    axm = Path(sys.executable).parent / "axm"
    result = subprocess.run(  # noqa: S603
        [str(axm), "smelt_count", "--model", "gpt-4o"],
        capture_output=True,
        text=True,
        input=text,
    )
    assert result.returncode == 0
    expected = len(tiktoken.encoding_for_model("gpt-4o").encode(text))
    token_count = result.stdout.split(" | ")[1].split()[0]
    assert int(token_count) == expected
