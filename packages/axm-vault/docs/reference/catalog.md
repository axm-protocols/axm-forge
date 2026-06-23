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

!!! warning "`SECRET`/`CONFIG` spec names must be valid `axm-config` keys"
    A `SECRET` spec persists a value-free presence sentinel keyed by
    `<name>_set`, and a `CONFIG` spec persists its value keyed by `<name>`;
    both go through `axm-config`, whose key charset is `^[A-Za-z0-9_]+$`
    (no `.` or `-`). A spec name carrying `.`/`-` could never round-trip, so
    building the `Catalog` (the path `load_catalog()` takes) **raises
    `ValueError`** naming the offending spec — a structural error caught at
    discovery rather than mid-`setup`. `NONSENSITIVE` specs are
    environment-only and exempt from this rule.

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
