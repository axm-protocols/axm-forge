"""Unit tests for the lazy package façade (PEP 562 ``__getattr__``)."""

from __future__ import annotations

import pytest

import axm_doctor


def test_getattr_resolves_public_symbol() -> None:
    """A name in ``__all__`` resolves to the real object from its submodule."""
    from axm_doctor.detect import detect_tool

    assert axm_doctor.detect_tool is detect_tool


def test_getattr_resolves_heavy_symbol() -> None:
    """A symbol from a heavy submodule (orchestrate/tools) resolves on access."""
    from axm_doctor.orchestrate import provision_missing
    from axm_doctor.tools import EnvDoctorTool

    assert axm_doctor.provision_missing is provision_missing
    assert axm_doctor.EnvDoctorTool is EnvDoctorTool


def test_getattr_unknown_name_raises_attribute_error() -> None:
    """An unknown attribute raises AttributeError, not KeyError/ImportError."""
    with pytest.raises(AttributeError, match="no attribute 'does_not_exist'"):
        _ = axm_doctor.does_not_exist


def test_dir_exposes_all_public_names() -> None:
    """``dir()`` surfaces every lazily-resolvable public name."""
    names = dir(axm_doctor)

    assert "detect_tool" in names
    assert "provision_missing" in names
    assert set(axm_doctor.__all__).issubset(names)
