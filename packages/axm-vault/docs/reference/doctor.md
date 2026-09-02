# Doctor & Tools

The **doctor** answers a single operational question for every credential in
the [catalog](catalog.md): *which layer would supply it, and is it present at
all* — **without ever reading or returning the value itself**. It is the
diagnostic, value-free counterpart of the [resolver](resolver.md): the
resolver hands back the value, the doctor hands back only its provenance.

## `doctor_data`

```python
from axm_vault import doctor_data

doctor_data()                 # whole catalog
doctor_data("axm-broker")     # only groups contributed by that package
```

`doctor_data(package=None, *, catalog=None, instance=None) -> Provenance`
returns a mapping keyed with the canonical
[`KeyringStore.username`](store.md) composition. A non-multi-instance group keeps
its `"{group.id}.{spec.name}"` key. A multi-instance group produces one entry per
declared instance and spec:

```python
{
    "broker.perso.api_key": {"layer": "keyring", "present": True},
    "broker.pro.api_key": {"layer": "missing", "present": False},
}
```

Passing `instance="pro"` bypasses discovery and reports only that instance. If a
multi-instance group has no declared instance source, it falls back to the
unsegmented key instead of disappearing from the report. Instance identities are
never concatenated manually: the canonical composer percent-escapes structural
separators, so instance `"a.b"` appears as the `"a%2Eb"` key segment.

| Field | Type | Meaning |
| -- | -- | -- |
| `layer` | `str` | The first layer to supply the credential — one of `env`, `file`, `keyring`, `default`, or `missing` |
| `present` | `bool` | `True` when any layer supplies it, `False` when none does |
| `keyring` | `str` (optional) | Present only as `"unavailable"` — added for a `SECRET` spec when the OS keyring backend is down (headless host); absent otherwise |

!!! note "Headless keyring is flagged, not fatal"
    On a host with no usable keyring backend, `doctor_data` does **not** crash:
    the [resolver](resolver.md) skips the keyring layer, and each `SECRET`
    spec's entry gains `"keyring": "unavailable"` so the outage is visible in
    the provenance report. Non-`SECRET` specs (which never touch the keyring)
    are not annotated.

    ```python
    {"broker.api_key": {"layer": "missing", "present": False, "keyring": "unavailable"}}
    ```

!!! danger "Never-leak invariant"
    `doctor_data` probes each layer for **presence only**: the value is
    reduced to a boolean the instant a layer answers (via
    [`Resolver.probe`](resolver.md)), so a plaintext secret never enters the
    report. Even for a present `SECRET` spec, the value appears **nowhere** in
    the output — this is a tested security invariant.

The `prompt` layer is excluded on purpose: provenance must never block on
stdin.

## MCP tools

Both tools are deterministic `axm.tools.base.AXMTool` implementations, so a
single entry-point declaration exposes each over MCP, the `axm` CLI and as a
DAG node. Neither tool ever serializes a `SECRET` value.

### `vault_doctor`

Returns value-free provenance — `ToolResult(success=True, data=doctor_data(...))`;
any error is shaped into `ToolResult(success=False, error=...)`.

```bash
axm vault_doctor                 # whole catalog
axm vault_doctor --package axm-broker
```

| Param | Type | Default | Notes |
| -- | -- | -- | -- |
| `package` | `str \| None` | `None` | Restrict to one package's groups |
| `instance` | `str \| None` | `None` | Report only this multi-instance identity and bypass instance discovery |

### `vault_set`

Stores a credential by `group.name`, routed by sensitivity, and reports only
the storage target — **the value is never echoed**.

```bash
axm vault_set --group broker --name api_key --value s3cr3t   # -> keyring:broker.api_key
```

| Sensitivity | Backend | `data["stored"]` |
| -- | -- | -- |
| `SECRET` | [`KeyringStore.set`](store.md) | `keyring:{group}.{name}` |
| `CONFIG` | `axm_config.set_` | `config:{group}.{name}` |
| `NONSENSITIVE` | — (rejected) | env-only -> `ToolResult(success=False, error=...)`, never stored |

| Param | Type | Default | Notes |
| -- | -- | -- | -- |
| `group` | `str` | `""` | Credential group id |
| `name` | `str` | `""` | Spec name within the group |
| `value` | `str` | `""` | The value to store (never echoed back) |
| `instance` | `str \| None` | `None` | Multi-instance segment (keyring only) |
