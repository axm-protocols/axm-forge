from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.practices.mirror import MirrorRule

pytestmark = pytest.mark.integration


def _write(p: Path, text: str = "") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_mirror_layout_partitions_missing_and_exempt(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "pkg" / "a.py", "x = 1\n")
    _write(tmp_path / "src" / "pkg" / "sub" / "b.py", "y = 2\n")
    _write(tmp_path / "tests" / "unit" / "test_a.py", "")
    _write(
        tmp_path / "pyproject.toml",
        '[tool.axm-audit.mirror]\nexempt_paths = ["sub/*"]\n',
    )

    result = MirrorRule().check(tmp_path)
    assert result.details is not None

    assert "b.py" in result.details["exempt"]
    assert "b.py" not in result.details["missing"]
    assert "a.py" not in result.details["missing"]


def test_flat_layout_falls_back_to_basename_match(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "pkg" / "a.py", "x = 1\n")
    _write(tmp_path / "tests" / "test_a.py", "")

    result = MirrorRule().check(tmp_path)
    assert result.details is not None

    assert "a.py" not in result.details["missing"]
    assert result.details["exempt"] == []


def test_empty_src_returns_empty_lists(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "tests").mkdir()

    result = MirrorRule().check(tmp_path)
    assert result.details is not None

    assert result.details["missing"] == []
    assert result.details["exempt"] == []
