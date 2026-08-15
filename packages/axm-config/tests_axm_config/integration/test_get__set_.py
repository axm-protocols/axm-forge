from __future__ import annotations

from pathlib import Path

import pytest

import axm_config
import axm_config.resolver as resolver_module
from axm_config import ConfigError, delete, get, set_
from axm_config.store import NamespaceStore

pytestmark = pytest.mark.integration


def test_delete_then_resolves_default() -> None:
    """AC4, AC5: delete removes the key, then get falls back to the default.

    Round-trips through the real ``~/.axm/<ns>.toml`` store (HOME redirected to
    a tmp dir by the autouse ``_isolated_home`` fixture).
    """
    set_("demo", "token", "secret")
    assert get("demo", "token", default="fallback") == "secret"

    delete("demo", "token")

    assert get("demo", "token", default="fallback") == "fallback"


def test_delete_absent_key_is_noop() -> None:
    """AC4: deleting an absent key is a silent no-op (no raise)."""
    delete("demo", "never_set")

    assert get("demo", "never_set", default="fallback") == "fallback"


@pytest.mark.parametrize(
    ("env_values", "expected", "raises"),
    [
        (
            {
                "AXM_EXECUTION__DEV__WORK_BACKEND": "openai",
                "AXM_EXECUTION__DEV__WORK_MODEL": "gpt-5",
                "AXM_EXECUTION__DEV__WORK_ANALYSIS_ENABLED": "true",
            },
            ("openai", "gpt-5", True),
            False,
        ),
        ({"AXM_EXECUTION__DEV__WORK_BACKEND": "openai"}, None, True),
        ({"AXM_EXECUTION__DEV__WORK_MODEL": "gpt-5"}, None, True),
        (
            {
                "AXM_EXECUTION__DEV__WORK_BACKEND": "",
                "AXM_EXECUTION__DEV__WORK_MODEL": "gpt-5",
            },
            None,
            True,
        ),
        (
            {
                "AXM_EXECUTION__DEV__WORK_BACKEND": " ",
                "AXM_EXECUTION__DEV__WORK_MODEL": " ",
            },
            None,
            True,
        ),
        (
            {"AXM_EXECUTION__DEV__WORK_ANALYSIS_ENABLED": " true"},
            None,
            True,
        ),
        (
            {"AXM_EXECUTION__DEV__WORK_ANALYSIS_ENABLED": "maybe"},
            None,
            True,
        ),
        (
            {"AXM_EXECUTION__DEV__WORK_ANALYSIS_ENABLED": "true"},
            ("file", "base", True),
            False,
        ),
        (
            {"AXM_EXECUTION__DEV__WORK_ANALYSIS_ENABLED": "TRUE"},
            ("file", "base", True),
            False,
        ),
        (
            {"AXM_EXECUTION__DEV__WORK_ANALYSIS_ENABLED": "1"},
            ("file", "base", True),
            False,
        ),
        (
            {"AXM_EXECUTION__DEV__WORK_ANALYSIS_ENABLED": "yes"},
            ("file", "base", True),
            False,
        ),
        (
            {"AXM_EXECUTION__DEV__WORK_ANALYSIS_ENABLED": "on"},
            ("file", "base", True),
            False,
        ),
        (
            {"AXM_EXECUTION__DEV__WORK_ANALYSIS_ENABLED": "false"},
            ("file", "base", False),
            False,
        ),
        (
            {"AXM_EXECUTION__DEV__WORK_ANALYSIS_ENABLED": "0"},
            ("file", "base", False),
            False,
        ),
        (
            {"AXM_EXECUTION__DEV__WORK_ANALYSIS_ENABLED": "no"},
            ("file", "base", False),
            False,
        ),
        (
            {"AXM_EXECUTION__DEV__WORK_ANALYSIS_ENABLED": "off"},
            ("file", "base", False),
            False,
        ),
        (
            {
                "AXM_EXECUTION_DEV_WORK_BACKEND": "wrong",
                "AXM_EXECUTION_DEV_WORK_MODEL": "wrong",
                "AXM_EXECUTION_DEV_WORK_ANALYSIS_ENABLED": "false",
            },
            ("file", "base", True),
            False,
        ),
    ],
)
def test_execution_policy_uses_canonical_env_names_and_atomic_layer_pair(
    monkeypatch: pytest.MonkeyPatch,
    env_values: dict[str, str],
    expected: tuple[str, str, bool] | None,
    raises: bool,
) -> None:
    """AC2: exact env names win by complete pair and parse booleans strictly."""
    store = NamespaceStore()
    store.write("execution.dev.work", "backend", "file")
    store.write("execution.dev.work", "model", "base")
    store.write("execution.dev.work", "analysis_enabled", True)

    canonical = {
        resolver_module._env_name("execution.dev.work", "backend"),
        resolver_module._env_name("execution.dev.work", "model"),
        resolver_module._env_name("execution.dev.work", "analysis_enabled"),
    }
    assert canonical == {
        "AXM_EXECUTION__DEV__WORK_BACKEND",
        "AXM_EXECUTION__DEV__WORK_MODEL",
        "AXM_EXECUTION__DEV__WORK_ANALYSIS_ENABLED",
    }

    for name in canonical | {
        "AXM_EXECUTION_DEV_WORK_BACKEND",
        "AXM_EXECUTION_DEV_WORK_MODEL",
        "AXM_EXECUTION_DEV_WORK_ANALYSIS_ENABLED",
    }:
        monkeypatch.delenv(name, raising=False)
    for name, value in env_values.items():
        monkeypatch.setenv(name, value)

    get_policy = axm_config.get_execution_policy
    if raises:
        with pytest.raises(ConfigError):
            get_policy("dev.work")
        return

    policy = get_policy("dev.work")
    assert (policy.backend, policy.model, policy.analysis_enabled) == expected


def test_execution_policy_env_names_are_documented_exactly() -> None:
    """AC5: README advertises only the canonical double-underscore names."""
    readme = (Path(__file__).parents[2] / "README.md").read_text(encoding="utf-8")
    canonical = {
        "AXM_EXECUTION__DEV__WORK_BACKEND",
        "AXM_EXECUTION__DEV__WORK_MODEL",
        "AXM_EXECUTION__DEV__WORK_ANALYSIS_ENABLED",
    }
    alternatives = {
        "AXM_EXECUTION_DEV_WORK_BACKEND",
        "AXM_EXECUTION_DEV_WORK_MODEL",
        "AXM_EXECUTION_DEV_WORK_ANALYSIS_ENABLED",
    }

    assert all(name in readme for name in canonical)
    assert all(name not in readme for name in alternatives)
