"""Reject malformed runner contracts before accepting read authority."""

from __future__ import annotations

import pytest

from axm.tools.dependency_reads import DependencyEnvironment


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"interpreter": "python"}, "interpreter must be absolute"),
        ({"interpreter": None}, "interpreter must be absolute"),
        ({"package_root": "project"}, "package_root must be absolute"),
        ({"package_root": 1}, "package_root must be absolute"),
        ({"pythonpath": "source"}, "pythonpath entries must be absolute"),
        ({"pythonpath": ["relative"]}, "pythonpath entries must be absolute"),
        ({"pythonpath": [None]}, "pythonpath entries must be absolute"),
    ],
)
def test_runner_wire_contract_rejects_invalid_locations(
    overrides: dict[str, object], message: str
) -> None:
    """Invalid runner declarations cannot become trusted dependency locations."""
    raw: dict[str, object] = {
        "interpreter": "/runner/bin/python",
        "package_root": "/project",
        **overrides,
    }
    with pytest.raises(ValueError, match=message):
        DependencyEnvironment.from_mapping(raw)
