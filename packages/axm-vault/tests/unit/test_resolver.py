from __future__ import annotations

from collections.abc import Iterator

import keyring
import pytest
from keyring.errors import NoKeyringError
from pydantic import BaseModel, SecretStr

from axm_vault.models import CredentialGroup, CredentialSpec, Sensitivity
from axm_vault.resolver import MissingCredentialError, Resolver, bind


class _UnavailableKeyring(keyring.backend.KeyringBackend):
    """Backend simulating a headless host with no usable keyring."""

    priority = 1

    def __init__(self) -> None:
        super().__init__()  # type: ignore[no-untyped-call]  # unstubbed keyring

    def get_password(self, service: str, username: str) -> str | None:
        raise NoKeyringError("No recommended backend was available")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise NoKeyringError("No recommended backend was available")

    def delete_password(self, service: str, username: str) -> None:
        raise NoKeyringError("No recommended backend was available")


@pytest.fixture
def unavailable_keyring() -> Iterator[_UnavailableKeyring]:
    """Swap the process-wide keyring for one that always raises NoKeyringError."""
    backend = _UnavailableKeyring()
    previous = keyring.get_keyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)


class _MemoryKeyring(keyring.backend.KeyringBackend):
    """In-memory keyring backend for unit tests (no OS Keychain)."""

    priority = 1

    def __init__(self) -> None:
        super().__init__()  # type: ignore[no-untyped-call]  # unstubbed keyring
        self._store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self._store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self._store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self._store.pop((service, username), None)


@pytest.fixture
def mem_keyring() -> Iterator[_MemoryKeyring]:
    """Swap the process-wide keyring for an in-memory backend."""
    backend = _MemoryKeyring()
    previous = keyring.get_keyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)


def _group(*specs: CredentialSpec, group_id: str = "svc") -> CredentialGroup:
    return CredentialGroup(
        id=group_id, package="pkg", title="Service", specs=tuple(specs)
    )


def test_env_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1, AC2: a present env var wins over all lower layers; layer=='env'."""
    spec = CredentialSpec(
        name="token", env="SVC_TOKEN", kind="token", default="fallback"
    )
    group = _group(spec)
    monkeypatch.setenv("SVC_TOKEN", "from-env")
    resolved = Resolver().resolve(group, "token")
    assert resolved.layer == "env"
    assert resolved.value == "from-env"
    assert resolved.spec is spec


def test_alias_after_canonical(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC2: canonical env unset, alias set -> resolves via the alias."""
    spec = CredentialSpec(
        name="token",
        env="SVC_TOKEN",
        kind="token",
        aliases=("LEGACY_TOKEN",),
        required=False,
    )
    group = _group(spec)
    monkeypatch.delenv("SVC_TOKEN", raising=False)
    monkeypatch.setenv("LEGACY_TOKEN", "via-alias")
    resolved = Resolver().resolve(group, "token")
    assert resolved.layer == "env"
    assert resolved.value == "via-alias"


def _patch_file_store(
    monkeypatch: pytest.MonkeyPatch, contents: dict[str, dict[str, object]]
) -> None:
    """Make the file tier read from ``contents`` instead of ``~/.axm`` (no I/O).

    Patches the file-only ``NamespaceStore.read`` surface vault delegates to;
    no env tier is ever consulted, mirroring the production read path.
    """
    from axm_config.store import NamespaceStore

    monkeypatch.setattr(
        NamespaceStore,
        "read",
        lambda _self, ns: dict(contents.get(ns, {})),
        raising=True,
    )


def test_file_tier_delegates_to_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC3: with no env, file tier reads the namespace file (delegated, file-only)."""
    spec = CredentialSpec(
        name="host",
        env="SVC_HOST",
        kind="host",
        sensitivity=Sensitivity.CONFIG,
        required=False,
    )
    group = _group(spec)
    monkeypatch.delenv("SVC_HOST", raising=False)
    _patch_file_store(monkeypatch, {"svc": {"host": "from-config"}})
    resolved = Resolver().resolve(group, "host")
    assert resolved.layer == "file"
    assert resolved.value == "from-config"


def test_file_layer_ignores_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1, AC2: an axm-config-style env var is NOT surfaced as the file layer.

    With no ``spec.env``/alias value and an empty namespace file, a value that
    exists only as an env var under axm-config's naming (``AXM_SVC_HOST``) must
    not leak into vault's ``file`` layer — provenance stays truthful.
    """
    spec = CredentialSpec(
        name="host",
        env="SVC_HOST",
        kind="host",
        sensitivity=Sensitivity.CONFIG,
        required=False,
        default="cfg-default",
    )
    group = _group(spec)
    monkeypatch.delenv("SVC_HOST", raising=False)
    monkeypatch.setenv("AXM_SVC_HOST", "leaked-via-config-env")
    _patch_file_store(monkeypatch, {})
    resolved = Resolver().resolve(group, "host")
    assert resolved.layer != "file"
    assert resolved.value != "leaked-via-config-env"
    assert resolved.layer == "default"
    assert resolved.value == "cfg-default"


def test_precedence_env_then_file_truthful(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC3: file-only value reports layer=='file'; spec.env wins as 'env'.

    Verifies the documented precedence ``env > file``: a value present only in
    the namespace file resolves as ``file``; once the same key is also set via
    vault's own ``spec.env`` it must resolve as ``env``.
    """
    spec = CredentialSpec(
        name="host",
        env="SVC_HOST",
        kind="host",
        sensitivity=Sensitivity.CONFIG,
        required=False,
    )
    group = _group(spec)
    _patch_file_store(monkeypatch, {"svc": {"host": "from-file"}})

    monkeypatch.delenv("SVC_HOST", raising=False)
    file_resolved = Resolver().resolve(group, "host")
    assert file_resolved.layer == "file"
    assert file_resolved.value == "from-file"

    monkeypatch.setenv("SVC_HOST", "from-env")
    env_resolved = Resolver().resolve(group, "host")
    assert env_resolved.layer == "env"
    assert env_resolved.value == "from-env"


def test_keyring_only_for_secret(
    monkeypatch: pytest.MonkeyPatch, mem_keyring: _MemoryKeyring
) -> None:
    """AC4: a CONFIG spec never consults the keyring even when a value sits there."""
    spec = CredentialSpec(
        name="host",
        env="SVC_HOST",
        kind="host",
        sensitivity=Sensitivity.CONFIG,
        required=False,
        default="cfg-default",
    )
    group = _group(spec)
    monkeypatch.delenv("SVC_HOST", raising=False)
    _patch_file_store(monkeypatch, {})
    from axm_vault.store import KeyringStore

    KeyringStore().set("svc", "host", "keyring-value")
    resolved = Resolver().resolve(group, "host")
    assert resolved.layer != "keyring"
    assert resolved.value == "cfg-default"


def test_secret_degrades_when_keyring_unavailable(
    monkeypatch: pytest.MonkeyPatch, unavailable_keyring: _UnavailableKeyring
) -> None:
    """AC2: a SECRET spec degrades gracefully when the keyring is unavailable.

    With env and file empty, resolution actually walks into the keyring layer,
    whose backend raises NoKeyringError. The resolver must swallow that, skip
    the keyring layer, and fall through to ``default`` rather than crash. A
    value present in env below it must still resolve normally.
    """
    spec = CredentialSpec(
        name="token",
        env="SVC_TOKEN",
        kind="token",
        sensitivity=Sensitivity.SECRET,
        required=False,
        default="fallback",
    )
    group = _group(spec)
    _patch_file_store(monkeypatch, {})

    # env/file empty -> resolution reaches the (unavailable) keyring layer and
    # must degrade to default without crashing.
    monkeypatch.delenv("SVC_TOKEN", raising=False)
    degraded = Resolver().resolve(group, "token")
    assert degraded.layer == "default"
    assert degraded.value == "fallback"

    # a value in env (above keyring) still resolves cleanly despite the outage.
    monkeypatch.setenv("SVC_TOKEN", "from-env")
    resolved = Resolver().resolve(group, "token")
    assert resolved.layer == "env"
    assert resolved.value == "from-env"


def test_missing_required_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC5: a required spec resolving to nothing raises MissingCredentialError."""
    spec = CredentialSpec(name="token", env="SVC_TOKEN", kind="token")
    group = _group(spec)
    monkeypatch.delenv("SVC_TOKEN", raising=False)
    _patch_file_store(monkeypatch, {})
    with pytest.raises(MissingCredentialError):
        Resolver().resolve(group, "token")


def test_default_for_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC5: a non-required spec falls back to spec.default; layer=='default'."""
    spec = CredentialSpec(
        name="region",
        env="SVC_REGION",
        kind="region",
        sensitivity=Sensitivity.CONFIG,
        required=False,
        default="eu-west",
    )
    group = _group(spec)
    monkeypatch.delenv("SVC_REGION", raising=False)
    _patch_file_store(monkeypatch, {})
    resolved = Resolver().resolve(group, "region")
    assert resolved.layer == "default"
    assert resolved.value == "eu-west"


def test_bind_secret_field_is_secretstr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC6: bind() builds the model; a SECRET field is a SecretStr instance."""

    class Creds(BaseModel):
        token: SecretStr
        region: str

    secret_spec = CredentialSpec(
        name="token", env="SVC_TOKEN", kind="token", sensitivity=Sensitivity.SECRET
    )
    config_spec = CredentialSpec(
        name="region",
        env="SVC_REGION",
        kind="region",
        sensitivity=Sensitivity.CONFIG,
    )
    group = _group(secret_spec, config_spec, group_id="svc")
    monkeypatch.setenv("SVC_TOKEN", "s3cret")
    monkeypatch.setenv("SVC_REGION", "eu-west")

    import importlib

    resolver_mod = importlib.import_module("axm_vault.resolver")
    monkeypatch.setattr(resolver_mod, "load_catalog", lambda: _Catalog({"svc": group}))
    bound = bind(Creds, "svc")
    assert isinstance(bound.token, SecretStr)
    assert bound.token.get_secret_value() == "s3cret"
    assert bound.region == "eu-west"


def test_absent_optional_secret_binds_none(
    monkeypatch: pytest.MonkeyPatch, mem_keyring: _MemoryKeyring
) -> None:
    """AC1: an absent optional SECRET binds to None, not SecretStr(\"\").

    With env, file, keyring and default all empty, an optional SECRET spec must
    resolve to ``None`` so the consumer model holds ``None`` (a plain
    ``if x is None`` check works) rather than an empty ``SecretStr``.
    """

    class Creds(BaseModel):
        token: SecretStr | None = None

    secret_spec = CredentialSpec(
        name="token",
        env="SVC_TOKEN",
        kind="token",
        sensitivity=Sensitivity.SECRET,
        required=False,
    )
    group = _group(secret_spec, group_id="svc")
    monkeypatch.delenv("SVC_TOKEN", raising=False)
    _patch_file_store(monkeypatch, {})

    import importlib

    resolver_mod = importlib.import_module("axm_vault.resolver")
    monkeypatch.setattr(resolver_mod, "load_catalog", lambda: _Catalog({"svc": group}))
    bound = bind(Creds, "svc")
    assert bound.token is None


def test_absent_optional_config_binds_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: an absent optional CONFIG binds to None, not the empty string.

    With env, file and default all empty, an optional CONFIG spec (the
    non-secret branch) must bind ``None`` so a consumer's ``if x is None``
    check works -- the same absence logic the SECRET branch already applies,
    now unified across both branches.
    """

    class Creds(BaseModel):
        host: str | None = None

    config_spec = CredentialSpec(
        name="host",
        env="SVC_HOST",
        kind="host",
        sensitivity=Sensitivity.CONFIG,
        required=False,
    )
    group = _group(config_spec, group_id="svc")
    monkeypatch.delenv("SVC_HOST", raising=False)
    _patch_file_store(monkeypatch, {})

    import importlib

    resolver_mod = importlib.import_module("axm_vault.resolver")
    monkeypatch.setattr(resolver_mod, "load_catalog", lambda: _Catalog({"svc": group}))
    bound = bind(Creds, "svc")
    assert bound.host is None


def test_empty_env_does_not_mask_lower(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC2: an empty env var (VAR='') does not win the env layer.

    An empty-string env value is treated as absent, so resolution falls
    through to the lower file layer instead of masking it with ``""``.
    """
    spec = CredentialSpec(
        name="host",
        env="SVC_HOST",
        kind="host",
        sensitivity=Sensitivity.CONFIG,
        required=False,
    )
    group = _group(spec)
    monkeypatch.setenv("SVC_HOST", "")
    _patch_file_store(monkeypatch, {"svc": {"host": "from-file"}})
    resolved = Resolver().resolve(group, "host")
    assert resolved.layer == "file"
    assert resolved.value == "from-file"


def test_from_prompt_secret_uses_getpass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: the prompt layer reads a SECRET via getpass (no visible echo).

    An interactive resolver resolving a SECRET spec from the prompt layer must
    route through ``getpass.getpass`` rather than ``input`` so the typed secret
    is never echoed to the terminal.
    """
    spec = CredentialSpec(
        name="token",
        env="SVC_TOKEN",
        kind="token",
        sensitivity=Sensitivity.SECRET,
        required=False,
        prompt="Enter token: ",
    )
    group = _group(spec)
    monkeypatch.delenv("SVC_TOKEN", raising=False)
    _patch_file_store(monkeypatch, {})

    used: dict[str, bool] = {"getpass": False, "input": False}

    def _fake_getpass(prompt: str = "") -> str:
        used["getpass"] = True
        return "typed-secret"

    def _fake_input(prompt: str = "") -> str:  # pragma: no cover - must not run
        used["input"] = True
        return "echoed-secret"

    import importlib

    resolver_mod = importlib.import_module("axm_vault.resolver")
    monkeypatch.setattr(resolver_mod, "getpass", _fake_getpass, raising=False)
    monkeypatch.setattr("builtins.input", _fake_input)

    resolved = Resolver(interactive=True).resolve(group, "token")
    assert resolved.layer == "prompt"
    assert resolved.value == "typed-secret"
    assert used["getpass"] is True
    assert used["input"] is False


class _Catalog:
    """Minimal stand-in for the catalog returned by load_catalog()."""

    def __init__(self, groups: dict[str, CredentialGroup]) -> None:
        self._groups = groups

    def group(self, group_id: str) -> CredentialGroup:
        return self._groups[group_id]
