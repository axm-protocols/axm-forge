"""Split from ``test_shared_helpers_io.py``."""

from pathlib import Path

from axm_audit.core.rules.test_quality._shared import get_init_all


def test_get_init_all_parses_dunder_all(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text('__all__ = ["X", "Y"]\n')
    result = get_init_all(tmp_path)
    assert result is not None
    assert set(result) == {"X", "Y"}


def test_get_init_all_missing_returns_none(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("x = 1\n")
    assert get_init_all(tmp_path) is None
