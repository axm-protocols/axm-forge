"""Unit tests for the language-backend registry."""

from __future__ import annotations

from pathlib import Path

from axm_ast.core.backends import backend_for, get_backend, supported_suffixes


def test_python_backend_resolves_for_py() -> None:
    """The .py suffix resolves to the python backend."""
    backend = get_backend(".py")
    assert backend is not None
    assert backend.name == "python"


def test_backend_for_uses_path_suffix(tmp_path: Path) -> None:
    """backend_for dispatches by the path's extension."""
    backend = backend_for(tmp_path / "module.py")
    assert backend is not None
    assert ".py" in backend.suffixes


def test_unsupported_suffix_returns_none() -> None:
    """An unknown extension resolves to no backend (no silent fallback)."""
    assert get_backend(".rs") is None


def test_python_suffix_always_supported() -> None:
    """Python is always registered regardless of optional backends."""
    assert ".py" in supported_suffixes()
