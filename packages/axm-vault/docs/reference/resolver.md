# Resolver

The **resolver** turns a value-less [catalog](catalog.md) into actual
credential values by walking a fixed precedence of layers and reporting
*which* layer answered. It is the read side of vault: the catalog declares
*what* a package needs, the resolver decides *where* each value comes from.

## Precedence

`Resolver.resolve(group, name, instance=None)` walks the layers in order and
returns the first that yields a value:

```
env  >  file  >  keyring  >  default  >  prompt
```

| Layer | Source | Notes |
| -- | -- | -- |
| `env` | `spec.env`, then each `spec.aliases` | Canonical env name wins over aliases; an empty variable is skipped, including before trying aliases |
| `file` | Active profile config table `[group]` via `axm_config.store.NamespaceStore` | Default file: `~/.axm/config.toml`; legacy `~/.axm/<group>.toml` fallback. Reads strings from disk, not config's environment-value tier |
| `keyring` | [`KeyringStore`](store.md) | Consulted **only** when `spec.sensitivity is Sensitivity.SECRET`; `CONFIG` never hits the keyring. On a headless host (no usable backend) the layer is skipped gracefully (see [below](#headless-keyring-graceful-degradation)) rather than crashing |
| `default` | `spec.default` | Used for required and optional specs; an empty string is a value |
| `prompt` | `getpass(spec.prompt)` (SECRET) / `input(spec.prompt)` (else) | Active only on an interactive resolver (`Resolver(interactive=True)`) with a `spec.prompt` set. A `SECRET` spec is read through `getpass` so the typed value is never echoed to the terminal; a non-secret spec uses a visible `input` prompt |

!!! note "File tier is file-only"
    The `file` layer reads the namespace table through `axm-config`'s
    `NamespaceStore`, with a legacy per-namespace file fallback. Vault delegates the
    `~/.axm` path itself (that stays `axm-config`'s single source of truth),
    and it never consults the environment from this layer. It deliberately
    does **not** call `axm_config.get`, whose `env > file` precedence (under
    `axm-config`'s own `AXM_*` naming) would let an environment value masquerade
    as a `file` value. The environment is sourced exclusively by the `env`
    layer (`spec.env` + aliases), keeping the reported provenance truthful.

## `Resolver`

```python
from axm_vault import Resolver

resolved = Resolver().resolve(group, "api_key")
resolved.value   # the resolved string
resolved.layer   # "env" | "file" | "keyring" | "default" | "prompt"
resolved.spec    # the originating CredentialSpec
```

| Member | Returns | Notes |
| -- | -- | -- |
| `Resolver(interactive=False)` | `Resolver` | `interactive=True` enables the `prompt` layer |
| `Resolver.PRECEDENCE` | `tuple[Layer, ...]` | `("env", "file", "keyring", "default", "prompt")` |
| `resolve(group, name, instance=None)` | [`Resolved`](#resolved) | First layer to answer wins |
| `probe(layer, spec, group, instance=None)` | `bool` | Value-free presence check for a single layer — reduces the value to a boolean the instant it is read; the seam the [doctor](doctor.md) uses to build provenance without leaking |
| `keyring_available()` | `bool` | Value-free probe of the OS keyring backend — `False` when no usable backend exists (headless host). The [doctor](doctor.md) uses it to flag `keyring: "unavailable"` |

A **required** spec that resolves to nothing raises `MissingCredentialError`;
a non-required spec falls back to `spec.default` with `layer == "default"`.

### Headless keyring — graceful degradation

When the OS keyring backend is unavailable (a headless CI runner with no
Keychain or secret service), [`KeyringStore`](store.md) raises a typed
[`KeyringUnavailableError`](store.md#keyringunavailableerror). The resolver
**catches it on the `keyring` layer and skips that layer**, so a `SECRET`
spec falls through to its lower layers (`default`, or `env`/`file` above) and
only typed keyring unavailability is suppressed. Missing required values and other backend or file errors still propagate. The outage is surfaced operationally by the
[doctor](doctor.md), which annotates the affected spec `keyring:
"unavailable"`.

## `Resolved`

The frozen outcome of a single resolution — it carries the resolved `value`,
the `layer` it came from and the originating `spec`. It never masks; callers
wrap secrets themselves (e.g. via [`as_secret`](secrets.md)).

```python
class Resolved(BaseModel):
    value: str | None
    layer: Layer        # Literal["env", "file", "keyring", "default", "prompt"]
    spec: CredentialSpec
```

## `bind`

`bind(model, group, instance=None)` resolves every spec in a group and builds
a consumer pydantic model from the results — each field is keyed by
`spec.name`, and `SECRET` specs are wrapped with `as_secret` so the bound
field is a `SecretStr`. A missing required spec propagates
`MissingCredentialError`.

An **absent optional** `SECRET` (a non-required spec with no real value in any
layer and no declared `default`) binds to `None` — not `SecretStr("")` — so a
consumer's `if creds.token is None` check works. Declare such a field as
`SecretStr | None`. An explicit (even empty) `default`, or a value sourced
from any real layer, is a genuine value and binds normally.

```python
from pydantic import BaseModel, SecretStr
from axm_vault import bind

class AcmeCreds(BaseModel):
    api_key: SecretStr   # SECRET spec -> SecretStr
    region: str          # CONFIG spec -> plain str

creds = bind(AcmeCreds, "acme")
creds.api_key.get_secret_value()   # the resolved secret
```

## `get`

`get(group, name, instance=None) -> str | None` is the module-level convenience over
the process-wide `resolver` singleton: it loads the catalog, resolves the
named credential and returns just the value.

```python
from axm_vault import get

api_key = get("acme", "api_key")
```

The singleton itself is exported as `resolver` (a non-interactive
`Resolver()`); construct your own `Resolver(interactive=True)` when you need
the prompt layer.

## `MissingCredentialError`

Raised when a *required* spec resolves to nothing across every layer. Carries
the `{group_id}.{name}` of the credential that could not be sourced.

## Reading and instance boundaries

The file layer reads strings for **every** sensitivity, including SECRET and NONSENSITIVE. Non-string TOML values are ignored; an empty string is accepted. `instance` selects only a keyring username: environment variables, file keys, defaults and prompts are shared across instances. A non-`None` default wins before an interactive prompt, even for a required spec.

A direct `Resolver().resolve(group, ...)` uses the supplied group without catalog validation. Module-level `get` and `bind` require a discovered group. A missing group/spec raises `KeyError`; binding also propagates consumer-model validation errors. `Resolved` is frozen but does not set `extra="forbid"`, unlike the catalog models. Its representation and dumps contain the plaintext value.
