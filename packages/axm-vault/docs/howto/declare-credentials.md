# Declare your package's credentials

This is the guide every consumer package (`axm-broker`, `axm-mail`, …) needs:
how to make vault aware of the credentials your package requires, so that
`axm-vault setup`, `get`, `bind`, and the doctor all work for it. You declare
**schema only** — never a value.

## 1. Write a provider that returns your groups

A provider is a plain callable returning `list[CredentialGroup]`. Put it in your
package (e.g. `src/axm_broker/credentials.py`):

```python
from __future__ import annotations

from axm_vault import CredentialGroup, CredentialSpec, Sensitivity


def provide_credentials() -> list[CredentialGroup]:
    return [
        CredentialGroup(
            id="broker",
            package="axm-broker",
            title="Broker API",
            specs=(
                CredentialSpec(
                    name="api_key",
                    env="BROKER_API_KEY",
                    kind="token",
                    sensitivity=Sensitivity.SECRET,
                ),
                CredentialSpec(
                    name="account_id",
                    env="BROKER_ACCOUNT_ID",
                    kind="id",
                    sensitivity=Sensitivity.NONSENSITIVE,
                    required=False,
                ),
                CredentialSpec(
                    name="region",
                    env="BROKER_REGION",
                    kind="str",
                    sensitivity=Sensitivity.CONFIG,
                    required=False,
                    default="eu",
                ),
            ),
        )
    ]
```

## 2. Choose the right `Sensitivity`

`Sensitivity` routes setup/set writes and selects keyring eligibility. It does not prevent plaintext reads or guarantee redaction:

| Sensitivity | Stored in | When to use |
|---|---|---|
| `SECRET` | OS keyring | API keys, tokens, passwords. Only SECRET specs consult keyring, but env/file/default can also supply their values. |
| `CONFIG` | axm-config (`~/.axm`) | Non-sensitive but per-install settings (a region, an account id you don't mind on disk). |
| `NONSENSITIVE` | *nothing* | Values provisioned through the environment: setup skips them and set rejects them. Resolver file/default/prompt layers remain eligible. |

## 3. Name specs and groups in the axm-config charset

The catalog applies the axm-config naming convention to `SECRET`/`CONFIG` specs; the
identifiers must be valid axm-config segments — validated at catalog load time
by `axm_config.validate_segment`:

- **`group.id`** is used verbatim as an axm-config **namespace**:
  `^[a-z0-9]+(\.[a-z0-9]+)*$` — lowercase alphanumeric segments joined by dots.
  No `_`, no `-`, no upper-case. (`broker` ✓, `axm_broker` ✗, `Broker` ✗.)
- **spec `name`** (for `SECRET`/`CONFIG`) is an axm-config **key**:
  `^[a-z0-9]+(_[a-z0-9]+)*$` — lowercase alphanumeric segments joined by a
  **single** `_`. No leading/trailing/doubled `_`, no `.`/`-`.
  (`api_key` ✓, `API_Key` ✗, `api__key` ✗, `api.key` ✗.)
- **`NONSENSITIVE`** spec names are env-only and exempt from the key charset
  (but the group id is still checked).

If any identifier violates its charset, `load_catalog()` raises at construction
— you find out immediately, not mid-`setup`.

## 4. Register the provider under the `axm.credentials` entry point

In your package's `pyproject.toml`:

```toml
[project.entry-points."axm.credentials"]
broker = "axm_broker.credentials:provide_credentials"
```

After a reinstall (`uv sync`), `load_catalog()` discovers it automatically —
the catalog aggregates every registered `axm.credentials` provider.

## Declare an external authentication dependency

Use the second catalog kind when your package depends on an external tool's
login session but must never read or provision its token. Implement the
runtime-checkable `AuthSource` contract in the package that owns the tool, then
attach an `AuthDependencySpec` to the same `CredentialGroup`:

```python
from axm_vault import AuthDependencySpec, AuthStatus, CredentialGroup

from axm_acme import acme_cli


class AcmeSessionSource:
    def status(self) -> AuthStatus:
        if not acme_cli.is_installed():
            return AuthStatus.TOOL_ABSENT
        if acme_cli.has_session():
            return AuthStatus.CONNECTED
        return AuthStatus.DISCONNECTED


group = CredentialGroup(
    id="acme",
    package="axm-acme",
    title="Acme",
    specs=(),
    auth_dependencies=(
        AuthDependencySpec(
            name="acme-session",
            source=AcmeSessionSource(),
        ),
    ),
)
```

Keep credentials and authentication dependencies separate: `all_specs()` feeds
resolution and provisioning, while `auth_dependencies()` returns descriptors; call their `status()` methods to observe external session state. An authentication dependency has no environment variable or
value accessor. If the supplied source does not implement `status()`,
construction raises `UnsupportedAuthDeclarationError`.

## 5. Use it

Once registered, all the vault surfaces work for your group:

```bash
axm-vault setup                 # interactively prompt + store every credential
axm-vault get broker api_key    # resolve (masked for SECRET unless --reveal)
axm-vault doctor                # value-free provenance: {layer, present} per spec
axm-vault rotate broker api_key   # hidden input; retains one .prev cycle
```

And in code, bind a typed model in one call:

```python
from pydantic import BaseModel, SecretStr

from axm_vault import bind


class BrokerCreds(BaseModel):
    api_key: SecretStr
    account_id: str | None = None
    region: str = "eu"


creds = bind(BrokerCreds, "broker")   # returns BrokerCreds — no cast needed
```

`bind` resolves every spec in the group, wraps `SECRET` fields in `SecretStr`,
and returns the concrete model type. A missing *required* spec raises
`MissingCredentialError`.

For a group with an `InstanceSource`, applications can enumerate and declare
account identities without entering the provisioning flow:

```python
from axm_vault import declare_instance, list_instances

list_instances(group)              # source order, or [] without a source
declare_instance(group, "pro")     # declares the name only
```

The vault wrapper only passes the instance name to the source. The source owns any I/O and must honor the no-secret declaration contract. Provisioning a credential
value remains a separate operation. Calling `declare_instance` without a source
raises `UnsupportedInstanceDeclarationError`; listing without one returns `[]`.

## Related

- [Catalog Models](../reference/models.md) — credentials, authentication dependencies, and groups
- [Resolver](../reference/resolver.md) — the layer precedence and `bind`
- [Architecture](../explanation/architecture.md) — why the keyring/config frontier exists
