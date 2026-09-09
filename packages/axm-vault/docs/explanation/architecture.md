# Architecture

Vault separates credential declarations, value resolution, storage, and provenance.
It returns plaintext when applications request values; it omits resolved values
from provenance reports. These are different contracts.

## Declaration and discovery

Packages contribute `CredentialGroup` objects through `axm.credentials`.
Credential specs describe names, environment aliases, sensitivity and defaults.
Defaults are ordinary strings: keeping secrets out of declarations is a provider
responsibility, not a model-enforced guarantee.

`load_catalog()` loads and calls providers, caches the resulting catalog, and
records loading/calling/type failures as rejections. Final identifier validation
can still fail the entire catalog. Duplicate ids use the last contribution in
discovery order. Providers execute in the process and are not sandboxed.
See [Catalog](../reference/catalog.md).

Authentication dependencies follow a separate traversal:
`Catalog.auth_dependencies()` returns descriptors whose `status()` delegates to
a source. Vault's credential doctor does not call these methods. The broader
`axm-doctor` package consumes authentication status for operational diagnostics.
An instance source similarly owns identity enumeration/declaration and its I/O.

## Resolution and storage

`Resolver` walks `env > file > keyring > default > prompt`.
Environment names come from the spec. Empty variables are skipped. The file
layer calls `axm_config.store.NamespaceStore`, which reads the namespace table
from the active profile's config file, with legacy per-namespace fallback,
without mixing config's own environment-value precedence into provenance.
Config owns home resolution and the TOML layout. It uses `Path.home() / ".axm"`;
`AXM_HOME` is not supported. Reading can create that directory and tighten its
permissions. The tutorial patches `Path.home()` explicitly for isolation.

| Sensitivity | Writes through setup/set | Eligible resolver layers |
|---|---|---|
| SECRET | Selected keyring backend | env, file, keyring, default, prompt |
| CONFIG | axm-config TOML | env, file, default, prompt |
| NONSENSITIVE | Rejected by set; skipped by setup | env, file, default, prompt |

NONSENSITIVE is described as environment-only for provisioning, but the resolver
does not restrict it to environment reads. File reads accept strings regardless
of sensitivity, including SECRET. This means a previously written plaintext file
can override a keyring credential. Do not interpret write routing as proof that
secrets can never reach disk.

`instance` affects keyring identity only. File keys, environment variables,
defaults and prompts are shared across instances. `group.multi` controls doctor
enumeration; it does not enforce instance use in the resolver.

## Provenance requires reads

`doctor_data` probes backend availability, then walks env/file/keyring/default
until a value is found for each spec. It reads the value and converts it to a
boolean. The report contains layer and presence, with a keyring-unavailable
annotation for SECRET specs when the typed availability probe fails.

No prompt-layer input is requested. Filesystem reads, backend interactions and
provider instance discovery still occur, and their errors can propagate.
`vault_doctor` catches failures into `ToolResult.error` and includes discovery
rejections in structured data. Its text summary lists skipped contributions only.
See [Doctor & Tools](../reference/doctor.md).

## Masking and disclosure boundaries

- `Resolved.value`, `get()`, and `KeyringStore.get()` return plaintext.
  `Resolved` representations and dumps are not masked.
- `bind()` wraps SECRET values with `SecretStr` before validating the consumer
  model. Default Pydantic displays/JSON mask it; explicit reveal and custom
  serializers can expose it. This is not encryption.
- Standalone `get` masks SECRET values unless `--reveal` is supplied.
  Command arguments and MCP inputs still carry any supplied plaintext.
- Successful provenance and mutation results omit resolved/stored values.
  Provider exception messages become rejection reasons and warning logs.
  Tool failures use `str(exc)`; arbitrary backend errors are not scrubbed.
- `redact` is an opt-in, exact-substring helper with a minimum length.
  It is not installed automatically around errors or logging.

## Persistence boundaries

The selected keyring backend supplies storage protection. Vault does not promise
that every installed backend is encrypted. Rotation retains one backup slot after
a successful serial operation; it has no multi-operation transaction, lock or
remote revocation. Deletion removes a single keyring slot and does not remove
file/env overrides or the previous backup.

`atomic_write` writes plaintext to an existing directory, replaces the target
atomically, applies mode 0600 and fsyncs the directory. It does not create a
credential store or encrypt the payload. A late error can occur after replacement.
See [Store](../reference/store.md).

## API placement

The [Python API](../reference/api/index.md) distinguishes root exports from
module-level implementation surfaces. The installed `axm.tools` entry points
provide generic CLI/MCP/DAG access. This package has no `axm.commands` entry
point or legacy YAML hook interface.
