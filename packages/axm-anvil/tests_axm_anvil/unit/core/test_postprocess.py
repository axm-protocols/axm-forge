"""Unit tests for the ``axm_anvil.core.postprocess`` public surface."""

from __future__ import annotations

from axm_anvil.core import postprocess


def test_postprocess_all_drops_ruff_fix() -> None:
    """AC2: `_ruff_fix` is no longer exported in `postprocess.__all__`."""
    assert "_ruff_fix" not in postprocess.__all__
    assert not [name for name in postprocess.__all__ if name.startswith("_")]


def test_ruff_fix_remains_module_importable() -> None:
    """AC2: dropping the export keeps the private helper module-internal."""
    assert callable(postprocess._ruff_fix)
