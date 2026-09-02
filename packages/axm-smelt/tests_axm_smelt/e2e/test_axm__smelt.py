from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import tiktoken

_AXM = Path(sys.executable).parent / "axm"


@pytest.mark.e2e
def _legacy_cli_help() -> None:
    """The AXMTool-derived CLI exposes help without the retired façade."""
    result = subprocess.run(  # noqa: S603
        [str(_AXM), "smelt", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout


@pytest.mark.e2e
def test_cli_preserves_utf8_input(tmp_path: Path) -> None:
    """The AXMTool-derived CLI preserves non-ASCII text end to end."""
    corpus = "café naïve résumé 漢字 こんにちは"
    input_path = tmp_path / "unicode.txt"
    input_path.write_text(corpus, encoding="utf-8")

    result = subprocess.run(  # noqa: S603
        [
            str(_AXM),
            "smelt",
            json.dumps(input_path.read_text(encoding="utf-8"), ensure_ascii=False),
        ],
        capture_output=True,
    )
    stdout = result.stdout.decode("utf-8")
    stderr = result.stderr.decode("utf-8")

    assert result.returncode == 0, stderr
    assert "café" in stdout
    assert "漢字" in stdout
    assert "こんにちは" in stdout


@pytest.mark.e2e
def test_cli_reads_redirected_text_for_smelt_and_check() -> None:
    """AC7: smelt and smelt_check report the redirected text's token count."""
    text = "alpha beta gamma delta epsilon"
    expected = len(tiktoken.get_encoding("o200k_base").encode(text))

    for command, pattern in (
        ("smelt", r"\|\s*(\d+)->"),
        ("smelt_check", r"\|\s*(\d+)\s+tok"),
    ):
        result = subprocess.run(  # noqa: S603
            [str(_AXM), command],
            capture_output=True,
            text=True,
            input=text,
        )

        assert result.returncode == 0, result.stderr
        match = re.search(pattern, result.stdout)
        assert match is not None, result.stdout
        assert expected > 0
        assert int(match.group(1)) == expected
