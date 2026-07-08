# Catalog

The **catalog** aggregates the [`CredentialGroup`](models.md#credentialgroup)
bundles contributed by packages and offers lookup over them. It is discovered
from the `axm.credentials` entry-point group.

!!! note "Empty by design"
    `axm-vault` itself contributes **no** credential groups. An empty catalog
    is the nominal state until other packages register an `axm.credentials`
    entry-point. `load_catalog()` therefore returns an empty `Catalog`
    gracefully — it never raises when nothing is registered.

## `load_catalog()`

```python
from axm_vault import load_catalog

catalog = load_catalog()
catalog.groups()   # -> [] when no package registered an axm.credentials EP
```

Reads the `axm.credentials` entry-points, calls each (every entry-point is a
callable returning `list[CredentialGroup]`) and indexes the groups by `id`.
The result is cached with `functools.cache`, so discovery runs **once** per
process.

A package contributes groups by declaring an entry-point in its
`pyproject.toml`:

```toml
[project.entry-points."axm.credentials"]
acme = "axm_acme.credentials:provide_groups"
```

where `provide_groups` is a callable returning `list[CredentialGroup]`.

!!! warning "Group ids and `SECRET`/`CONFIG` spec names must be valid `axm-config` segments"
    A `CONFIG` spec persists its value in `axm-config` keyed by `<name>` under
    the namespace `group.id`, so both identifiers must round-trip through
    `axm-config`. Validation delegates to the canonical
    `axm_config.validate_segment`:

    - **`group.id`** is a *namespace*: `^[a-z0-9]+(\.[a-z0-9]+)*$` — lowercase
      alphanumeric segments joined by dots (no `_`, `-`, or upper-case).
    - **`SECRET`/`CONFIG` spec `name`** is a *key*: `^[a-z0-9]+(_[a-z0-9]+)*$` —
      lowercase alphanumeric segments joined by a single `_` (no leading /
      trailing / doubled `_`, no `.`/`-`).

    An identifier that could never round-trip makes building the `Catalog` (the
    path `load_catalog()` takes) **raise `ValueError`** naming the offender — a
    structural error caught at discovery rather than mid-`setup`.
    `NONSENSITIVE` spec names are environment-only and exempt (the group id is
    still checked).

## `Catalog`

An in-memory index of credential groups, keyed by group `id`. Frozen
(`frozen=True`) and strict (`extra="forbid"`).

| Method | Returns | Notes |
| -- | -- | -- |
| `Catalog(groups=...)` | `Catalog` | Build from a tuple of `CredentialGroup` |
| `group(gid)` | `CredentialGroup` | Raises `KeyError` (clear message) if unknown |
| `groups()` | `list[CredentialGroup]` | Every registered group |
| `for_package(package)` | `list[CredentialGroup]` | Groups contributed by `package` |
| `all_specs()` | `list[tuple[str, CredentialSpec]]` | `(group_id, spec)` pairs, flattened |

```python
from axm_vault import Catalog, CredentialGroup, CredentialSpec

group = CredentialGroup(
    id="acme",
    package="axm-acme",
    title="Acme",
    specs=(CredentialSpec(name="api_key", env="ACME_API_KEY", kind="token"),),
)
catalog = Catalog(groups=(group,))

catalog.group("acme")            # -> CredentialGroup(...)
catalog.group("missing")         # -> raises KeyError
catalog.for_package("axm-acme")  # -> [CredentialGroup(...)]
catalog.all_specs()              # -> [("acme", CredentialSpec(...))]
```
