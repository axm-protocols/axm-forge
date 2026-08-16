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
    namespace = resolver_module._execution_namespace("dev.work")
    store.write(namespace, "backend", "file")
    store.write(namespace, "model", "base")
    store.write(namespace, "analysis_enabled", True)

    canonical = {
        resolver_module._env_name(namespace, "backend"),
        resolver_module._env_name(namespace, "model"),
        resolver_module._env_name(namespace, "analysis_enabled"),
    }
    assert canonical == {
        "AXM_EXECUTION__V1__6465762E776F726B_BACKEND",
        "AXM_EXECUTION__V1__6465762E776F726B_MODEL",
        "AXM_EXECUTION__V1__6465762E776F726B_ANALYSIS_ENABLED",
    }

    for name in canonical | {
        "AXM_EXECUTION_DEV_WORK_BACKEND",
        "AXM_EXECUTION_DEV_WORK_MODEL",
        "AXM_EXECUTION_DEV_WORK_ANALYSIS_ENABLED",
    }:
        monkeypatch.delenv(name, raising=False)
    legacy_prefix = "AXM_EXECUTION__DEV__WORK_"
    for name, value in env_values.items():
        if name.startswith(legacy_prefix):
            key = name.removeprefix(legacy_prefix).lower()
            name = resolver_module._env_name(namespace, key)
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


def test_listing_filters_malformed_leaves_without_weakening_targeted_reads() -> None:
    """AC1: listing skips each invalid leaf while direct lookup stays strict."""
    store = NamespaceStore()

    policy_namespace = resolver_module._execution_namespace
    store.write(policy_namespace("a.analysis"), "analysis_enabled", True)
    store.write(policy_namespace("b.backend"), "backend", "openai")
    store.write(policy_namespace("b.backend"), "model", "gpt-5")
    store.write(policy_namespace("c.full"), "backend", "anthropic")
    store.write(policy_namespace("c.full"), "model", "claude")
    store.write(policy_namespace("c.full"), "analysis_enabled", False)

    store.write(policy_namespace("zparent.child"), "unknown", "value")
    store.write(policy_namespace("zempty"), "temporary", True)
    delete(policy_namespace("zempty"), "temporary")
    store.write(policy_namespace("zunknown"), "unknown", "value")
    store.write(policy_namespace("zmixedunknown"), "backend", "openai")
    store.write(policy_namespace("zmixedunknown"), "model", "gpt-5")
    store.write(policy_namespace("zmixedunknown"), "unknown", "value")
    store.write(policy_namespace("zbackendonly"), "backend", "openai")
    store.write(policy_namespace("zmodelonly"), "model", "gpt-5")
    store.write(policy_namespace("zblankbackend"), "backend", "")
    store.write(policy_namespace("zblankbackend"), "model", "gpt-5")
    store.write(policy_namespace("zblankmodel"), "backend", "openai")
    store.write(policy_namespace("zblankmodel"), "model", " ")
    store.write(policy_namespace("znonboolean"), "analysis_enabled", "true")
    store.write(policy_namespace("zwrongbackendtype"), "backend", 42)
    store.write(policy_namespace("zwrongbackendtype"), "model", "gpt-5")
    store.write(policy_namespace("zwrongmodeltype"), "backend", "openai")
    store.write(policy_namespace("zwrongmodeltype"), "model", 42)

    policies = axm_config.list_execution_policies()

    assert list(policies) == ["a.analysis", "b.backend", "c.full"]
    assert (
        policies["a.analysis"].backend,
        policies["a.analysis"].model,
        policies["a.analysis"].analysis_enabled,
    ) == (None, None, True)
    assert (
        policies["b.backend"].backend,
        policies["b.backend"].model,
        policies["b.backend"].analysis_enabled,
    ) == ("openai", "gpt-5", None)
    assert (
        policies["c.full"].backend,
        policies["c.full"].model,
        policies["c.full"].analysis_enabled,
    ) == ("anthropic", "claude", False)

    with pytest.raises(ConfigError):
        axm_config.get_execution_policy("zbackendonly")


_INVALID_EXECUTION_POLICY_IDENTIFIERS = (
    "",
    "orchestrate._audit",
    "orchestrate.audit_",
    "orchestrate.contre__audit",
    "Orchestrate.audit",
    "orchestrate.contre-audit",
    ".orchestrate",
    "orchestrate.",
    "orchestrate..audit",
)


@pytest.mark.parametrize(
    "invalid_ticket_type",
    _INVALID_EXECUTION_POLICY_IDENTIFIERS,
)
def test_invalid_execution_policy_preserves_configuration_bytes(
    invalid_ticket_type: str,
) -> None:
    """AC1: rejecting an invalid policy ID leaves persisted bytes unchanged."""
    set_("seed", "value", "unchanged")
    axm_config.set_execution_policy(
        "orchestrate.contre_audit",
        backend="openai",
        model="gpt-5",
    )
    config_path = NamespaceStore()._config_path()
    before = config_path.read_bytes()

    with pytest.raises(ConfigError):
        axm_config.set_execution_policy(
            invalid_ticket_type,
            backend="mlx",
            model="qwen",
        )

    assert config_path.read_bytes() == before


def test_legacy_collision_spellings_use_distinct_canonical_namespaces() -> None:
    """AC2: legacy-colliding IDs persist and look up as distinct exact IDs."""
    expected = {
        "dev.python_work": ("openai", "gpt-5", True),
        "dev.python.work": ("mlx", "qwen", False),
    }
    for ticket_type, (backend, model, analysis_enabled) in expected.items():
        axm_config.set_execution_policy(
            ticket_type,
            backend=backend,
            model=model,
            analysis_enabled=analysis_enabled,
        )

    payload = NamespaceStore()._config_path().read_text(encoding="utf-8")
    for ticket_type in expected:
        token = ticket_type.encode("utf-8").hex()
        assert f"[execution.v1.{token}]" in payload
    assert "dev.python_work" not in payload
    assert "dev.python.work" not in payload

    listed = axm_config.list_execution_policies()
    assert set(listed) == set(expected)
    for ticket_type, values in expected.items():
        policy = axm_config.get_execution_policy(ticket_type)
        assert (policy.backend, policy.model, policy.analysis_enabled) == values
        assert listed[ticket_type] == policy


def _write_legacy_policy(
    ticket_type: str,
    *,
    backend: str,
    model: str,
    analysis_enabled: bool,
) -> tuple[Path, bytes]:
    payload = (
        f'backend = "{backend}"\n'
        f'model = "{model}"\n'
        f"analysis_enabled = {str(analysis_enabled).lower()}\n"
    ).encode()
    path = Path.home() / ".axm" / f"execution.{ticket_type}.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path, payload


def test_canonical_policy_and_tombstone_leave_legacy_bytes_unchanged() -> None:
    """AC1: canonical set/delete/set wins without mutating legacy bytes."""
    legacy_path, legacy_bytes = _write_legacy_policy(
        "dev.work",
        backend="legacy",
        model="base",
        analysis_enabled=True,
    )

    legacy = axm_config.get_execution_policy("dev.work")
    assert (legacy.backend, legacy.model, legacy.analysis_enabled) == (
        "legacy",
        "base",
        True,
    )

    axm_config.set_execution_policy(
        "dev.work",
        backend="canonical",
        model="new",
        analysis_enabled=False,
    )
    canonical = axm_config.get_execution_policy("dev.work")
    assert (canonical.backend, canonical.model, canonical.analysis_enabled) == (
        "canonical",
        "new",
        False,
    )
    assert legacy_path.read_bytes() == legacy_bytes

    axm_config.delete_execution_policy("dev.work")

    deleted = axm_config.get_execution_policy("dev.work")
    assert deleted.model_dump() == {
        "backend": None,
        "model": None,
        "analysis_enabled": None,
    }
    token = b"dev.work".hex()
    assert NamespaceStore().read(f"execution.v1.{token}") == {"tombstone": "v1"}
    assert legacy_path.read_bytes() == legacy_bytes

    axm_config.set_execution_policy(
        "dev.work",
        backend="restored",
        model="latest",
        analysis_enabled=True,
    )

    restored = axm_config.get_execution_policy("dev.work")
    assert (restored.backend, restored.model, restored.analysis_enabled) == (
        "restored",
        "latest",
        True,
    )
    assert NamespaceStore().read(f"execution.v1.{token}") == {
        "backend": "restored",
        "model": "latest",
        "analysis_enabled": True,
    }
    assert legacy_path.read_bytes() == legacy_bytes


def test_environment_precedence_around_valid_and_malformed_tombstones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: complete env wins; exact tombstones mask, malformed ones do not."""
    _write_legacy_policy(
        "dev.work",
        backend="legacy",
        model="base",
        analysis_enabled=True,
    )
    axm_config.delete_execution_policy("dev.work")
    token = b"dev.work".hex()
    env_prefix = f"AXM_EXECUTION__V1__{token.upper()}"
    env = {
        f"{env_prefix}_BACKEND": "environment",
        f"{env_prefix}_MODEL": "override",
        f"{env_prefix}_ANALYSIS_ENABLED": "false",
    }
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    overridden = axm_config.get_execution_policy("dev.work")
    assert (
        overridden.backend,
        overridden.model,
        overridden.analysis_enabled,
    ) == ("environment", "override", False)

    for name in env:
        monkeypatch.delenv(name)

    masked = axm_config.get_execution_policy("dev.work")
    assert masked.model_dump() == {
        "backend": None,
        "model": None,
        "analysis_enabled": None,
    }

    set_(f"execution.v1.{token}", "tombstone", "v2")

    fallback = axm_config.get_execution_policy("dev.work")
    assert (fallback.backend, fallback.model, fallback.analysis_enabled) == (
        "legacy",
        "base",
        True,
    )


def test_listing_strictly_decodes_masks_and_filters_storage_entries() -> None:
    """AC3: listing exposes strict IDs and policies, never tokens or tombstones."""
    _write_legacy_policy(
        "legacy.only",
        backend="legacy",
        model="only",
        analysis_enabled=True,
    )
    _write_legacy_policy(
        "masked.policy",
        backend="legacy",
        model="shadowed",
        analysis_enabled=True,
    )
    _write_legacy_policy(
        "masked.delete",
        backend="legacy",
        model="deleted",
        analysis_enabled=True,
    )
    _write_legacy_policy(
        "malformed.fallback",
        backend="legacy",
        model="fallback",
        analysis_enabled=False,
    )

    axm_config.set_execution_policy(
        "canonical.only",
        backend="canonical",
        model="only",
        analysis_enabled=False,
    )
    axm_config.set_execution_policy(
        "masked.policy",
        backend="canonical",
        model="winner",
        analysis_enabled=False,
    )
    axm_config.delete_execution_policy("masked.delete")

    malformed_token = b"malformed.fallback".hex()
    set_(f"execution.v1.{malformed_token}", "tombstone", "v2")
    invalid_payload_token = b"invalid.payload".hex()
    set_(f"execution.v1.{invalid_payload_token}", "backend", "incomplete")
    set_("execution.v1.zz", "backend", "invalid-token")
    set_("execution.v1.zz", "model", "invalid-token")

    policies = axm_config.list_execution_policies()

    assert list(policies) == [
        "canonical.only",
        "legacy.only",
        "malformed.fallback",
        "masked.policy",
    ]
    assert policies["canonical.only"].model_dump() == {
        "backend": "canonical",
        "model": "only",
        "analysis_enabled": False,
    }
    assert policies["legacy.only"].model_dump() == {
        "backend": "legacy",
        "model": "only",
        "analysis_enabled": True,
    }
    assert policies["malformed.fallback"].model_dump() == {
        "backend": "legacy",
        "model": "fallback",
        "analysis_enabled": False,
    }
    assert policies["masked.policy"].model_dump() == {
        "backend": "canonical",
        "model": "winner",
        "analysis_enabled": False,
    }
    assert "masked.delete" not in policies
    assert "invalid.payload" not in policies
    assert "zz" not in policies
    assert all("tombstone" not in policy.model_dump() for policy in policies.values())


@pytest.mark.parametrize(
    "selected",
    (
        "orchestrate.contre_audit",
        "dev.python_work",
        "research.paper_note",
    ),
)
def test_public_policy_operations_preserve_original_identifiers(
    selected: str,
) -> None:
    """AC3: set/get/list/delete round-trip every supported original ID."""
    expected = {
        "orchestrate.contre_audit": ("openai", "gpt-5", True),
        "dev.python_work": ("mlx", "qwen", False),
        "research.paper_note": ("anthropic", "claude", None),
    }
    for ticket_type, (backend, model, analysis_enabled) in expected.items():
        axm_config.set_execution_policy(
            ticket_type,
            backend=backend,
            model=model,
            analysis_enabled=analysis_enabled,
        )

    selected_policy = axm_config.get_execution_policy(selected)
    assert (
        selected_policy.backend,
        selected_policy.model,
        selected_policy.analysis_enabled,
    ) == expected[selected]
    assert set(axm_config.list_execution_policies()) == set(expected)

    axm_config.delete_execution_policy(selected)

    deleted = axm_config.get_execution_policy(selected)
    assert deleted.model_dump() == {
        "backend": None,
        "model": None,
        "analysis_enabled": None,
    }
    remaining = axm_config.list_execution_policies()
    assert set(remaining) == set(expected) - {selected}
