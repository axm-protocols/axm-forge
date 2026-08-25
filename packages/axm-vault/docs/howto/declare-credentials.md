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

`Sensitivity` decides *where the value is stored* and *whether it may leak*:

| Sensitivity | Stored in | When to use |
|---|---|---|
| `SECRET` | OS keyring | API keys, tokens, passwords — anything that must never touch disk in the clear. Consulted only by the `keyring` layer; masked everywhere. |
| `CONFIG` | axm-config (`~/.axm`) | Non-sensitive but per-install settings (a region, an account id you don't mind on disk). |
| `NONSENSITIVE` | *nothing* | Environment-only values. They are never prompted nor stored — storing them would create a second, stale source of truth. |

## 3. Name specs and groups in the axm-config charset

Because a `SECRET`/`CONFIG` value round-trips through `axm-config`, the
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

## 5. Use it

Once registered, all the vault surfaces work for your group:

```bash
axm-vault setup                 # interactively prompt + store every credential
axm-vault get broker api_key    # resolve (masked for SECRET unless --reveal)
axm-vault doctor                # value-free provenance: {layer, present} per spec
axm-vault rotate broker api_key <new>   # rotate a SECRET (keeps one .prev cycle)
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

## Related

- [Catalog Models](../reference/models.md) — every field of `CredentialSpec` / `CredentialGroup`
- [Resolver](../reference/resolver.md) — the layer precedence and `bind`
- [Architecture](../explanation/architecture.md) — why the keyring/config frontier exists
