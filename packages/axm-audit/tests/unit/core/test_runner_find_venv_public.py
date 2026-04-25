"""AC3: core.runner.find_venv promoted to public."""

from __future__ import annotations


def test_find_venv_public() -> None:
    """find_venv is importable as a public callable."""
    from axm_audit.core.runner import find_venv

    assert callable(find_venv)


def test_find_venv_private_alias_removed() -> None:
    """_find_venv shim is gone from core.runner."""
    from axm_audit.core import runner

    assert not hasattr(runner, "_find_venv"), (
        "deprecated private alias _find_venv still exposed"
    )
