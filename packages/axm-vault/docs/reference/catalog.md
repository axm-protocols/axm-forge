# Catalog

The **catalog** aggregates the [`CredentialGroup`](models.md#credentialgroup)
bundles contributed by packages. A group may carry resolvable credential specs
and value-less authentication dependencies; both are discovered through the
same `axm.credentials` entry-point group but exposed by distinct accessors.

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

Discovery is isolated per contribution. If loading or calling one entry-point
fails, its provider is not callable, it yields an item other than a
`CredentialGroup`, or one of its groups carries an invalid identifier (see
below), `load_catalog()` skips only that contribution. It emits a
`WARNING`, records a typed `CatalogRejection`, and continues serving every
conforming group. The same policy is available directly through
`groups_from_provider(entry_point, provider)` for callers that already hold a
provider object.

## `groups_from_provider()`

```python
from axm_vault import groups_from_provider

groups, rejection = groups_from_provider("acme", provide_groups)
# conforming:  ((CredentialGroup(...), ...), None)
# defective:   ((), CatalogRejection(entry_point="acme", reason="..."))
```

The public, single-contribution judgement that `load_catalog()` applies to every
entry-point. It never raises for a contribution defect and is **all-or-nothing**:
one defect (non-callable provider, provider exception, non-`CredentialGroup`
item, invalid identifier) discards the whole contribution, valid sibling groups
included. Groups are checked in provider order and specs in declaration order,
stopping at the first failure, so the rejection is deterministic and equal to
the one `load_catalog()` records for the same entry-point. Callers such as
`axm-doctor` use it to apply the exact same rule without copying it.

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

    During discovery, a contribution declaring an identifier that could never
    round-trip is **rejected as a whole**: `load_catalog()` records a
    `CatalogRejection` whose reason names the offender
    (`invalid credential identifier 'Bad_ID': ...`) and keeps every other
    contribution. Building a `Catalog` directly with such an identifier still
    **raises `ValueError`** (a pydantic `ValidationError`) — the rule is a
    type-level guarantee with a single implementation shared by both paths.
    `NONSENSITIVE` spec names are environment-only and exempt (the group id is
    still checked).

## `CatalogRejection`

A frozen, strict record describing one contribution excluded during discovery.
It contains the entry-point `entry_point` and a non-empty diagnostic `reason`.
The reason can contain the original provider exception message. Providers must keep credentials out of diagnostics; vault does not redact arbitrary exception text.

## `Catalog`

An in-memory collection of credential groups. Direct construction retains duplicates and `group(gid)` returns the first match; discovery deduplicates by id, retaining the last contribution in entry-point iteration order. Frozen
(`frozen=True`) and strict (`extra="forbid"`).

| Method | Returns | Notes |
| -- | -- | -- |
| `Catalog(groups=..., rejections=...)` | `Catalog` | Build from credential groups and optional typed discovery rejections |
| `group(gid)` | `CredentialGroup` | Raises `KeyError` (clear message) if unknown |
| `groups()` | `list[CredentialGroup]` | Every registered group |
| `rejections()` | `list[CatalogRejection]` | Contributions skipped during discovery, with their reason |
| `for_package(package)` | `list[CredentialGroup]` | Groups contributed by `package` |
| `all_specs()` | `list[tuple[str, CredentialSpec]]` | Credential `(group_id, spec)` pairs only, flattened |
| `auth_dependencies()` | `list[AuthDependencySpec]` | Authentication dependencies only, flattened |

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
catalog.auth_dependencies()      # -> [] for this credential-only group
```

## Discovery boundaries

Providers may return any iterable of `CredentialGroup`, though a list is the recommended declaration. If any yielded item is invalid, or any group carries an invalid group id or storable spec name, the whole provider contribution is rejected; the rest of discovery is unaffected. Duplicate ids are not errors: the last discovered group wins, so providers must use distinct ids rather than depend on installation order.

`load_catalog()` is cached; restart a long-lived process after installing or changing providers. Importing/loading/calling a third-party provider executes its code and can perform I/O. Vault does not sandbox providers. `groups_from_provider` is exported at the package root (`from axm_vault import groups_from_provider`).
