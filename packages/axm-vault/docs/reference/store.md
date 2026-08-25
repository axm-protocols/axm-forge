# Store

The **store** is a thin, stateless wrapper over the OS keyring
([`keyring`](https://github.com/jaraco/keyring)). Every AXM secret lives
under a single fixed service (`SERVICE = "axm-vault"`) and a composed
`username` of the form `{group}.{instance?}.{name}`, so one credential
group can host several named values, optionally namespaced by instance
(e.g. several mail accounts).

!!! note "Keyring only — no files"
    `KeyringStore` deliberately knows **nothing** about files or `~/.axm`.
    Any on-disk layout (config directories, token files) is owned by
    `axm-config`. The single disk primitive vault exposes is
    [`atomic_write`](#atomic_write), for the OAuth refresh-token rotation
    case — and even then the destination directory is supplied by the
    caller; vault never resolves or creates it.

## `KeyringStore`

Store and retrieve secrets in the OS keyring under `SERVICE`. The store is
stateless: every call delegates to the process-wide `keyring` backend, so
tests can swap in an in-memory backend via `keyring.set_keyring(...)`
without touching the real Keychain.

| Method | Returns | Notes |
| -- | -- | -- |
| `KeyringStore.username(group, name, instance=None)` | `str` | Compose the keyring username (`{group}.{name}` or `{group}.{instance}.{name}`) |
| `set(group, name, value, instance=None)` | `None` | Store `value` under the composed username; raises [`KeyringUnavailableError`](#keyringunavailableerror) on a headless host |
| `get(group, name, instance=None)` | `str \| None` | The stored secret, or `None` if absent; raises [`KeyringUnavailableError`](#keyringunavailableerror) on a headless host |
| `delete(group, name, instance=None)` | `None` | Remove the credential (no-op if absent); raises [`KeyringUnavailableError`](#keyringunavailableerror) on a headless host |

!!! warning "Headless host — no usable keyring"
    When no OS keyring backend is available (e.g. a headless CI runner with
    no Keychain or secret service), `set`/`get`/`delete` raise a typed
    [`KeyringUnavailableError`](#keyringunavailableerror) instead of leaking a
    raw backend traceback. The [resolver](resolver.md) catches it and degrades
    the `keyring` layer gracefully; the [doctor](doctor.md) flags the spec
    `keyring: "unavailable"`.

```python
from axm_vault import KeyringStore

store = KeyringStore()

store.set("linear", "api_key", "s3cr3t")
store.get("linear", "api_key")            # "s3cr3t"
store.get("linear", "missing")            # None

# Instance namespacing — two accounts under the same group/name never collide
store.set("mail", "password", "pw-personal", instance="personal")
store.set("mail", "password", "pw-work", instance="work")
store.get("mail", "password", instance="personal")   # "pw-personal"
store.get("mail", "password")                         # None (no plain entry)
```

The `username` helper is the pure composition rule. `.` is the structural
separator, so each segment is percent-escaped before joining (a literal `.`
becomes `%2E`, and `%` itself becomes `%25`). This keeps the mapping
**injective**: a `.` embedded inside a segment can never make two distinct
`(group, name, instance)` tuples collapse onto the same username. Dot-free
segments are left untouched, so existing usernames are unchanged.

```python
KeyringStore.username("linear", "api_key")                    # "linear.api_key"
KeyringStore.username("mail", "password", instance="work")    # "mail.work.password"

# A dot inside a segment is escaped, so these never collide:
KeyringStore.username("a.b", "c")                             # "a%2Eb.c"
KeyringStore.username("a", "b.c")                             # "a.b%2Ec"
KeyringStore.username("a", "c", instance="b")                 # "a.b.c"
```

### Testing without the real Keychain

Because the store is stateless over the process-wide backend, an in-memory
`keyring.backend.KeyringBackend` can be installed in a fixture so CI never
touches the OS Keychain:

```python
import keyring
from keyring.backend import KeyringBackend

class MemoryKeyring(KeyringBackend):
    priority = 1.0
    def __init__(self):
        super().__init__()
        self._store = {}
    def get_password(self, service, username):
        return self._store.get((service, username))
    def set_password(self, service, username, password):
        self._store[(service, username)] = password
    def delete_password(self, service, username):
        self._store.pop((service, username), None)

keyring.set_keyring(MemoryKeyring())   # subsequent KeyringStore calls stay in memory
```

## `rotate_secret`

```python
rotate_secret(group: str, name: str, value: str, instance: str | None = None) -> None
```

Rotate a keyring secret while retaining the previous value for **one cycle**:
the prior cycle's backup is purged first, the current value (if any) is copied
to the reserved `{name}.prev` slot, then `value` is written over `{name}`.
Retention is strictly one cycle — a stale `.prev` never lingers across
rotations. Keeping the previous secret one rotation lets a caller fall back
during an in-flight credential roll. No value is ever returned or logged. This
is the central function the [`axm-vault rotate`](cli.md) command delegates to.

!!! note "`.prev` is a reserved suffix"
    The `.prev` suffix names the rotation backup slot, so it must not collide
    with a real spec name or instance. Calling `rotate_secret` with a `name`
    that already ends in `.prev` raises `ValueError`.

```python
from axm_vault import rotate_secret

rotate_secret("broker", "api_key", "new-s3cr3t")
# logical slots: broker.api_key = "new-s3cr3t", broker.api_key.prev = <old value>
# (the backup slot's `.` is escaped in the stored username: broker.api_key%2Eprev)

rotate_secret("broker", "api_key", "newer")
# broker.api_key = "newer", broker.api_key.prev = "new-s3cr3t" (one-cycle: the
# first .prev is purged, not accumulated)
```

## `atomic_write`

```python
atomic_write(path: Path | str, data: str, *, encoding: str = "utf-8") -> None
```

Write `data` to `path` atomically: the write goes to a temporary file in the
destination directory, is flushed and `fsync`-ed, then atomically renamed
over `path` with `os.replace`, so a concurrent reader never observes a
partially written file. After the rename the parent directory is itself
`fsync`-ed, so the new directory entry survives a crash that strikes right
after `os.replace` — without that, the file content could reach disk while the
rename is lost. Intended for the OAuth refresh-token rotation case.

!!! warning "Directory must exist"
    The destination directory must already exist — `atomic_write` does not
    create it. That is `axm-config`'s responsibility.

!!! note "Owner-only permissions (`0600`)"
    Because the payload is a secret (refresh token), the final file is always
    mode `0600` regardless of the process umask: `mkstemp` creates the temp
    file `0600` and `atomic_write` re-applies `chmod 0600` after `os.replace`,
    so the renamed inode is never group/world-readable.

```python
from pathlib import Path
from axm_vault import atomic_write

atomic_write(Path("/run/axm/token.json"), '{"refresh": "abc"}')
# crash-safe overwrite: readers see either the old file or the new one, never a partial
```

## `KeyringUnavailableError`

```python
class KeyringUnavailableError(RuntimeError): ...
```

Raised by `KeyringStore.set`/`get`/`delete` (and therefore `rotate_secret`)
when the OS keyring backend is unavailable — a headless host with no Keychain
or secret service, where `keyring` would otherwise report *"No recommended
backend was available"*. It replaces the raw backend traceback with a typed,
actionable error so callers can degrade the keyring layer gracefully.

!!! danger "Never-leak invariant"
    The error message is fixed and actionable; the original backend exception
    is chained (`raise ... from exc`) but **never interpolated** into the
    message, so no credential value can leak through an error path.

## `SERVICE`

The fixed keyring service name under which every AXM secret is stored:
`"axm-vault"`.
