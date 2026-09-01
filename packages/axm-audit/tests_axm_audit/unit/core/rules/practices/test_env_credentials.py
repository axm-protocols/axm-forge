from __future__ import annotations

import ast
import importlib
from types import ModuleType

import pytest


def _load_module() -> ModuleType:
    return importlib.import_module("axm_audit.core.rules.practices.env_credentials")


def test_credential_name_patterns_drive_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: credential names are recognised through the declared patterns."""
    env_credentials = _load_module()

    assert isinstance(env_credentials.CREDENTIAL_NAME_PATTERNS, tuple)
    assert env_credentials.is_credential_env_var("ANTHROPIC_API_KEY")
    assert not env_credentials.is_credential_env_var("AXM_LOG_LEVEL")

    monkeypatch.setattr(env_credentials, "CREDENTIAL_NAME_PATTERNS", ())
    assert not env_credentials.is_credential_env_var("ANTHROPIC_API_KEY")


def test_boolean_only_credential_read_is_ignored() -> None:
    """AC2: retain a bound value read but discard a boolean-only read."""
    env_credentials = _load_module()
    tree = ast.parse(
        """\
import os
key = os.environ.get("S2_API_KEY")
if not os.environ.get("S2_API_KEY"):
    pass
"""
    )

    reads = env_credentials.find_env_credential_value_reads(
        tree,
        module_path="axm_bib.providers.s2",
    )

    assert len(reads) == 1
    assert reads[0].lineno == 2


def test_all_value_consuming_forms_are_reported() -> None:
    """AC3: report argument, return, f-string, and subscript value reads."""
    env_credentials = _load_module()
    tree = ast.parse(
        """\
import os
consume(os.getenv("S2_API_KEY"))
def load():
    return os.environ.get("S2_API_KEY")
message = f"{os.getenv('S2_API_KEY')}"
key = os.environ["S2_API_KEY"]
"""
    )

    reads = env_credentials.find_env_credential_value_reads(
        tree,
        module_path="axm_bib.providers.s2",
    )

    assert len(reads) == 4
    assert [read.lineno for read in reads] == [2, 4, 5, 6]


def test_credential_layer_patterns_drive_exemption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: credential-layer module paths are recognised through patterns."""
    env_credentials = _load_module()

    assert isinstance(env_credentials.CREDENTIAL_LAYER_MODULE_PATTERNS, tuple)
    assert env_credentials.is_credential_layer_module("axm_vault.resolver")
    assert not env_credentials.is_credential_layer_module("axm_bib.providers.s2")

    monkeypatch.setattr(
        env_credentials,
        "CREDENTIAL_LAYER_MODULE_PATTERNS",
        (),
    )
    assert not env_credentials.is_credential_layer_module("axm_vault.resolver")


def test_non_credential_setting_is_ignored() -> None:
    """AC5: ignore ordinary settings while retaining credential value reads."""
    env_credentials = _load_module()
    tree = ast.parse(
        """\
import os
level = os.getenv("AXM_LOG_LEVEL")
key = os.getenv("S2_API_KEY")
"""
    )

    reads = env_credentials.find_env_credential_value_reads(
        tree,
        module_path="axm_bib.providers.s2",
    )

    assert len(reads) == 1
    assert reads[0].env_var == "S2_API_KEY"
