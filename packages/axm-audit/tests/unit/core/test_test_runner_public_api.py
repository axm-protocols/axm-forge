"""AC2: test_runner parsing helpers exposed under public names."""

from __future__ import annotations

import pytest

_PUBLIC = (
    "build_test_report",
    "parse_coverage",
    "parse_failures",
    "parse_json_report",
    "parse_collector_errors",
    "build_pytest_cmd",
)


def test_test_runner_public_parsing_api() -> None:
    """All parsing helpers importable as public symbols."""
    from axm_audit.core import test_runner

    for name in _PUBLIC:
        assert hasattr(test_runner, name), f"missing public symbol: {name}"
        assert callable(getattr(test_runner, name))


@pytest.mark.parametrize("name", _PUBLIC)
def test_private_alias_removed(name: str) -> None:
    """Underscore-prefixed aliases removed (no shim left behind)."""
    from axm_audit.core import test_runner

    assert not hasattr(test_runner, f"_{name}"), (
        f"deprecated private alias _{name} still exposed"
    )
