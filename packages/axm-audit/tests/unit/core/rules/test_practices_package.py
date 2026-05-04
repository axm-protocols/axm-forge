from __future__ import annotations

import importlib
from pathlib import Path

import pytest


@pytest.fixture
def registry():
    import axm_audit.core.rules  # noqa: F401  (fire decorators)
    from axm_audit.core.rules.base import get_registry

    return get_registry()


def test_practices_rules_registered(registry):
    bucket = registry["practices"]
    names = {cls.__name__ for cls in bucket}
    assert {
        "DocstringCoverageRule",
        "BareExceptRule",
        "BlockingIORule",
        "TestMirrorRule",
    } <= names


def test_security_pattern_rule_in_security_bucket(registry):
    bucket = registry["security"]
    names = {cls.__name__ for cls in bucket}
    assert "SecurityPatternRule" in names


def test_practices_module_path_canonical():
    mod = importlib.import_module("axm_audit.core.rules.practices")
    assert hasattr(mod, "__path__"), (
        "axm_audit.core.rules.practices must be a package, not a module file"
    )


def test_practices_legacy_module_gone():
    import axm_audit.core.rules.practices as practices_pkg

    assert practices_pkg.__file__ is not None
    assert Path(practices_pkg.__file__).name == "__init__.py"
