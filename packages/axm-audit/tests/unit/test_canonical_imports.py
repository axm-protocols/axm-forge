from __future__ import annotations

import importlib

import pytest
from pydantic import BaseModel


def test_canonical_imports_resolve() -> None:
    """AC2: canonical paths expose register_rule, ProjectRule, get_registry,
    Severity, AuditResult, CheckResult."""
    from axm_audit.core.rules.base import (
        ProjectRule,
        get_registry,
        register_rule,
    )
    from axm_audit.models.results import AuditResult, CheckResult, Severity

    decorator = register_rule("lint")
    assert callable(decorator)
    assert Severity.ERROR.value == "error"
    assert issubclass(CheckResult, BaseModel)
    assert issubclass(AuditResult, BaseModel)
    assert isinstance(get_registry(), dict)
    assert ProjectRule.__name__ == "ProjectRule"


@pytest.mark.parametrize(
    "shim",
    [
        "axm_audit.core.registry",
        "axm_audit.core.severity",
        "axm_audit.core.models",
        "axm_audit.core.rules.registry",
    ],
)
def test_shim_modules_are_gone(shim: str) -> None:
    """AC1: the four re-export shim modules must not be importable."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(shim)
