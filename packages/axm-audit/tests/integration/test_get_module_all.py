"""Split from ``test_shared_helpers_io.py``."""

from pathlib import Path

from axm_audit.core.rules.test_quality._shared import get_module_all


def test_get_module_all_for_submodule(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("")
    (tmp_path / "src" / "pkg" / "core.py").write_text('__all__ = ["foo", "bar"]\n')
    result = get_module_all(tmp_path, "pkg.core")
    assert result is not None
    assert set(result) == {"foo", "bar"}
