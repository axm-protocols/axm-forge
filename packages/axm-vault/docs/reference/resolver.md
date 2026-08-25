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
| `env` | `spec.env`, then each `spec.aliases` | Canonical env name wins over aliases; a present env var beats every lower layer |
| `file` | `~/.axm/<group>.toml` (via `axm_config.store.NamespaceStore`) | **File-only**: reads the on-disk namespace file, never the environment — provenance reported as `file` is always file-backed |
| `keyring` | [`KeyringStore`](store.md) | Consulted **only** when `spec.sensitivity is Sensitivity.SECRET`; `CONFIG` never hits the keyring. On a headless host (no usable backend) the layer is skipped gracefully (see [below](#headless-keyring-graceful-degradation)) rather than crashing |
| `default` | `spec.default` | Fallback for non-required specs |
| `prompt` | `getpass(spec.prompt)` (SECRET) / `input(spec.prompt)` (else) | Active only on an interactive resolver (`Resolver(interactive=True)`) with a `spec.prompt` set. A `SECRET` spec is read through `getpass` so the typed value is never echoed to the terminal; a non-secret spec uses a visible `input` prompt |

!!! note "File tier is file-only"
    The `file` layer reads the per-namespace TOML file under `~/.axm`
    through `axm-config`'s `NamespaceStore` — vault never resolves the
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
resolution never crashes. The outage is surfaced operationally by the
[doctor](doctor.md), which annotates the affected spec `keyring:
"unavailable"`.

## `Resolved`

The frozen outcome of a single resolution — it carries the resolved `value`,
the `layer` it came from and the originating `spec`. It never masks; callers
wrap secrets themselves (e.g. via [`as_secret`](secrets.md)).

```python
class Resolved(BaseModel):
    value: str
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

`get(group, name, instance=None) -> str` is the module-level convenience over
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
