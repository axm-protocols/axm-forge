# Catalog Models

The credential catalog is described by **value-less** pydantic models: they
declare the *schema* of a credential (where it lives, how sensitive it is,
whether it is required) but **never hold a secret value**. This is a security
invariant — no field on any model stores a credential value.

All models are frozen (`frozen=True`) and reject unknown fields
(`extra="forbid"`).

## `Sensitivity`

A `StrEnum` classifying how sensitive a credential is:

| Member | Value |
| -- | -- |
| `SECRET` | `"secret"` |
| `CONFIG` | `"config"` |
| `NONSENSITIVE` | `"nonsensitive"` |

## `Layer`

A type alias for the resolution layers a credential may be sourced from:

```python
type Layer = Literal["env", "file", "keyring", "default", "prompt"]
```

## `CredentialSpec`

The schema for a single credential.

| Field | Type | Default |
| -- | -- | -- |
| `name` | `str` | — (required) |
| `env` | `str` | — (required) |
| `kind` | `str` | — (required) |
| `sensitivity` | `Sensitivity` | `Sensitivity.SECRET` |
| `required` | `bool` | `True` |
| `default` | `str \| None` | `None` |
| `prompt` | `str \| None` | `None` |
| `aliases` | `tuple[str, ...]` | `()` |

```python
from axm_vault import CredentialSpec

spec = CredentialSpec(name="api_key", env="ACME_API_KEY", kind="token")
```

## `CredentialGroup`

A bundle of the credential specs a package requires.

| Field | Type | Default |
| -- | -- | -- |
| `id` | `str` | — (required) |
| `package` | `str` | — (required) |
| `title` | `str` | — (required) |
| `specs` | `tuple[CredentialSpec, ...]` | — (required) |
| `multi` | `bool` | `False` |

### `CredentialGroup.spec(name)`

Return the `CredentialSpec` named `name`. Raises `KeyError` if no spec with
that name exists in the group.

```python
from axm_vault import CredentialGroup, CredentialSpec

group = CredentialGroup(
    id="acme",
    package="axm-acme",
    title="Acme",
    specs=(CredentialSpec(name="api_key", env="ACME_API_KEY", kind="token"),),
)

group.spec("api_key")   # -> CredentialSpec(...)
group.spec("missing")   # -> raises KeyError
```
