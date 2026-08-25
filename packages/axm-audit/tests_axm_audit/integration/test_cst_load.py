"""Split from ``test_io_primitives.py``."""

from pathlib import Path

from axm_audit.core.fix.io_primitives import cst_load


def test_cst_load_returns_none_on_parse_error(tmp_path: Path) -> None:
    """AC3: cst_load returns None when libcst cannot parse the source."""
    path = tmp_path / "broken.py"
    path.write_text("def broken(\n")
    assert cst_load(path) is None
