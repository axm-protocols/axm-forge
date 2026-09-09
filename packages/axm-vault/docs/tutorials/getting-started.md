# Resolve a synthetic credential in isolation

This tutorial declares a group and observes resolution and masking without
accessing your keyring or configuration. Use Python 3.12+ in a disposable process.

## Install

```bash
uv add axm-vault
axm-vault --help
```

Package version metadata is available through the public packaging interface:

```python
from importlib.metadata import version

print(version("axm-vault"))
```

## Configure an isolated backend before reading anything

Save the following complete example as `vault_demo.py`. All values are synthetic.
The explicit patch of `Path.home()` and in-memory keyring ensure that lower-layer
probes do not consult your real settings or keychain.

```python
from __future__ import annotations

import os
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

import keyring
from keyring.backend import KeyringBackend


class MemoryKeyring(KeyringBackend):
    priority = 1.0

    def __init__(self):
        self.values = {}

    def get_password(self, service, username):
        return self.values.get((service, username))

    def set_password(self, service, username, password):
        self.values[(service, username)] = password

    def delete_password(self, service, username):
        self.values.pop((service, username), None)


keyring.set_keyring(MemoryKeyring())

from axm_vault import (
    Catalog, CredentialGroup, CredentialSpec, KeyringStore,
    Resolver, as_secret, doctor_data,
)

with TemporaryDirectory() as synthetic_home, patch(
    "pathlib.Path.home", return_value=Path(synthetic_home)
):
    os.environ["VAULT_DOCS_TOKEN"] = "synthetic-env"
    group = CredentialGroup(
        id="docsdemo",
        package="docs-example",
        title="Documentation example",
        specs=(CredentialSpec(
            name="token", env="VAULT_DOCS_TOKEN", kind="token",
        ),),
    )
    store = KeyringStore()
    store.set("docsdemo", "token", "synthetic-keyring")

    resolved = Resolver().resolve(group, "token")
    assert resolved.layer == "env"
    assert resolved.value == "synthetic-env"
    masked = as_secret(resolved.value)
    assert str(masked) == "**********"

    del os.environ["VAULT_DOCS_TOKEN"]
    assert Resolver().resolve(group, "token").layer == "keyring"

    report = doctor_data(catalog=Catalog(groups=(group,)))
    assert report == {"docsdemo.token": {"layer": "keyring", "present": True}}
    assert "synthetic-keyring" not in str(report)
    print("Synthetic resolution and provenance verified.")
```

Run it in the project's environment:

```bash
uv run python vault_demo.py
```

The direct resolver accepts your in-memory group. Module-level `get` and `bind`
instead use the installed provider catalog; creating a local variable named
`group` does not register it.

## Next steps

[Register your package's provider](../howto/declare-credentials.md) before using
catalog-based commands. Consult [Resolver](../reference/resolver.md) for optional
values and instance limits, and [CLI](../reference/cli.md) for provisioning.
