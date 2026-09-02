from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import tiktoken


@pytest.mark.e2e
def _legacy_count_with_model_name() -> None:
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


@pytest.mark.e2e
def test_count_reads_redirected_text() -> None:
    """AC6: smelt_count counts the actual non-empty text redirected on stdin."""
    text = "alpha beta gamma delta epsilon"
    axm = Path(sys.executable).parent / "axm"

    result = subprocess.run(  # noqa: S603
        [str(axm), "smelt_count"],
        capture_output=True,
        text=True,
        input=text,
    )

    assert result.returncode == 0, result.stderr
    expected = len(tiktoken.get_encoding("o200k_base").encode(text))
    token_count = result.stdout.split(" | ")[1].split()[0]
    assert expected > 0
    assert int(token_count) == expected


@pytest.mark.e2e
def test_count_rejects_missing_input_path(tmp_path: Path) -> None:
    """AC8: smelt_count fails noisily when --input-path designates no file."""
    input_path = tmp_path / "absent.txt"
    axm = Path(sys.executable).parent / "axm"

    result = subprocess.run(  # noqa: S603
        [str(axm), "smelt_count", "--input-path", str(input_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert str(input_path) in result.stderr
    assert "unknown option" not in result.stderr.lower()
