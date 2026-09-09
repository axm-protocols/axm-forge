# Catalog Models

The catalog is described by **value-less** pydantic models. A
`CredentialSpec` declares the schema of a resolvable credential; an
`AuthDependencySpec` reports only the state of an external authentication
session. Keep real secrets out of declarations: `CredentialSpec.default` is an ordinary string and is not protected or rejected for SECRET specs.

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

## Authentication dependencies

An authentication dependency represents a session managed by an external tool.
The `AuthDependencySpec.status()` method delegates observation to its source. The contract asks sources not to read authentication material; vault cannot enforce the I/O behavior of arbitrary provider code.

### `AuthStatus`

`AuthStatus` is a `StrEnum` with three distinct observations:

| Member | Value | Meaning |
| -- | -- | -- |
| `CONNECTED` | `"connected"` | The tool and its authenticated session are present. |
| `DISCONNECTED` | `"disconnected"` | The tool is present but has no usable session. |
| `TOOL_ABSENT` | `"tool_absent"` | The tool itself is not installed or available. |

### `AuthSource`

A runtime-checkable protocol supplied by the declaring package. Its sole method,
`status() -> AuthStatus`, observes the package-owned tool. Passing an object that
does not implement this protocol raises `UnsupportedAuthDeclarationError` when
the dependency is constructed.

### `AuthDependencySpec`

A frozen, strict model with a required `name`. Its source is accepted at
construction and retained privately: the only authentication operation exposed
by the spec is `status() -> AuthStatus`. In particular, there is no `resolve`,
`value`, `secret`, `get`, or `env_var` surface.

```python
from axm_vault import AuthDependencySpec, AuthStatus


class AcmeSessionSource:
    def status(self) -> AuthStatus:
        return AuthStatus.CONNECTED


dependency = AuthDependencySpec(
    name="acme-session",
    source=AcmeSessionSource(),
)
assert dependency.status() is AuthStatus.CONNECTED
```

## `InstanceSource`

A runtime-checkable capability implemented by packages that declare named
instances for a credential group. Vault defines only the interface; the
declaring package remains responsible for locating and creating its instances.

| Method | Contract |
| -- | -- |
| `list_instances()` | Return the available instance names as a `Sequence[str]`. |
| `declare(instance)` | Declare the named instance and return `None`. |

Objects providing both methods satisfy `isinstance(source, InstanceSource)`.
The protocol carries no credential values and has no knowledge of a package's
configuration layout.

## Instance operations

The public helpers call the capability carried by a `CredentialGroup`:

```python
from axm_vault import declare_instance, list_instances

names = list_instances(group)
declare_instance(group, "pro")
```

`list_instances(group) -> list[str]` preserves the source's names and order. It
returns an empty list when the group has no instance source, including for a
multi-instance group.

`declare_instance(group, instance) -> None` delegates only the clear-text
instance name to the source. It neither prompts nor reads or writes a credential
value. When the group has no source, it raises
`UnsupportedInstanceDeclarationError` and names the group id in the message.

## `CredentialGroup`

A bundle of the credential specs a package requires.

| Field | Type | Default |
| -- | -- | -- |
| `id` | `str` | — (required) |
| `package` | `str` | — (required) |
| `title` | `str` | — (required) |
| `specs` | `tuple[CredentialSpec, ...]` | — (required) |
| `auth_dependencies` | `tuple[AuthDependencySpec, ...]` | `()` |
| `multi` | `bool` | `False` |
| `instances` | `InstanceSource \| None` | `None` |

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

`kind` is descriptive metadata, not a validator or converter; the resolver supplies strings. `AuthDependencySpec.status()` delegates directly and does not validate the source's returned enum at runtime. Instance helpers likewise delegate behavior and errors; the no-secret contract must be respected by the source implementation.
