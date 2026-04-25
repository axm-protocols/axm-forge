"""AC1: coupling helpers extracted as public symbols in dedicated submodule."""

from __future__ import annotations

import pytest

_EXPECTED = (
    "tarjan_scc",
    "classify_module_role",
    "build_coupling_result",
    "extract_imports",
    "read_coupling_config",
    "strip_prefix",
    "parse_overrides",
    "safe_int",
)


@pytest.mark.parametrize("name", _EXPECTED)
def test_coupling_module_exports(name: str) -> None:
    """Each promoted helper is importable from coupling submodule."""
    # Without leading underscore.
    from axm_audit.core.rules.architecture import coupling

    assert hasattr(coupling, name), f"missing public symbol: {name}"
    assert callable(getattr(coupling, name))


def test_coupling_private_aliases_removed() -> None:
    """Old underscore-prefixed names must not survive on the new module."""
    from axm_audit.core.rules.architecture import coupling

    for name in _EXPECTED:
        assert not hasattr(coupling, f"_{name}"), (
            f"deprecated alias _{name} still exposed on coupling module"
        )
