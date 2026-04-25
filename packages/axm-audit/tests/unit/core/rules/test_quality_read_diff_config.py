"""AC4: read_diff_config promoted to public; _get_audit_targets stays private."""

from __future__ import annotations


def test_read_diff_config_public() -> None:
    """read_diff_config is importable as a public callable."""
    from axm_audit.core.rules.quality import read_diff_config

    assert callable(read_diff_config)


def test_read_diff_config_private_alias_removed() -> None:
    """Underscore alias is gone."""
    from axm_audit.core.rules import quality

    assert not hasattr(quality, "_read_diff_config"), (
        "deprecated private alias _read_diff_config still exposed"
    )


def test_get_audit_targets_remains_private() -> None:
    """AC4 leaves _get_audit_targets private — guard against promotion."""
    from axm_audit.core.rules import quality

    assert not hasattr(quality, "get_audit_targets"), (
        "_get_audit_targets must remain private (drives only one rule, no test usage)"
    )
