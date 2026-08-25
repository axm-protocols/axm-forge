from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def test_cli_old_name_rejected() -> None:
    result = subprocess.run(
        ["uv", "run", "axm-smelt", "compact", "--strategies", "dedup_values"],  # noqa: S607
        capture_output=True,
        text=True,
        input='{"a":"b"}',
    )
    assert result.returncode != 0
    assert "dedup_values" in (result.stderr + result.stdout).lower()


def test_compact_non_ascii_file(tmp_path: Path) -> None:
    """AC3: compacting a non-ASCII file preserves its content as utf-8."""
    content = "café naïve résumé 漢字 こんにちは"
    src = tmp_path / "input.txt"
    src.write_text(content, encoding="utf-8")
    out = tmp_path / "output.txt"

    result = subprocess.run(  # noqa: S603
        ["uv", "run", "axm-smelt", "compact", "--file", str(src), "--output", str(out)],  # noqa: S607
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    written = out.read_text(encoding="utf-8")
    for token in ("café", "漢字", "こんにちは"):
        assert token in written
