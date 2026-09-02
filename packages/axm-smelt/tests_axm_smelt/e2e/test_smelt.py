from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_AXM = Path(sys.executable).parent / "axm"


@pytest.mark.e2e
def test_cli_old_name_rejected() -> None:
    result = subprocess.run(  # noqa: S603
        [str(_AXM), "smelt", "compact", "--strategies", "dedup_values"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "dedup_values" in (result.stderr + result.stdout).lower()


@pytest.mark.e2e
def test_compact_non_ascii_file(tmp_path: Path) -> None:
    """AC3: compacting a non-ASCII file preserves its content as utf-8."""
    content = "café naïve résumé 漢字 こんにちは"
    src = tmp_path / "input.txt"
    src.write_text(content, encoding="utf-8")
    out = tmp_path / "output.txt"

    result = subprocess.run(  # noqa: S603
        [
            str(_AXM),
            "smelt",
            "compact",
            "--file",
            str(src),
            "--output",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    written = out.read_text(encoding="utf-8")
    for token in ("café", "漢字", "こんにちは"):
        assert token in written
