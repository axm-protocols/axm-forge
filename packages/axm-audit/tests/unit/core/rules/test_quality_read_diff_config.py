"""AC4: read_diff_config promoted to public; _get_audit_targets stays private."""

from __future__ import annotations

import pytest


def test_read_diff_config_public() -> None:
    """read_diff_config is importable as a public callable."""
    from axm_audit.core.rules.quality import read_diff_config

    assert callable(read_diff_config)


@pytest.mark.parametrize(
    ("attr", "reason"),
    [
        pytest.param(
            "_read_diff_config",
            "deprecated private alias _read_diff_config still exposed",
            id="private_alias_removed",
        ),
        pytest.param(
            "get_audit_targets",
            "_get_audit_targets must remain private"
            " (drives only one rule, no test usage)",
            id="get_audit_targets_remains_private",
        ),
    ],
)
def test_quality_module_attribute_absent(attr: str, reason: str) -> None:
    """AC4 surface: certain attributes must NOT be exposed on the quality module."""
    from axm_audit.core.rules import quality

    assert not hasattr(quality, attr), reason
