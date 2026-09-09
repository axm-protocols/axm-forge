# Doctor & Tools

The **doctor** answers a single operational question for every credential in
the [catalog](catalog.md): *which layer would supply it, and is it present at
all* — **without including the resolved value in provenance**. Probes read environment, file and keyring values, then reduce them to booleans. It is the
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

The three tools are `axm.tools.base.AXMTool` implementations, so a
single entry-point declaration exposes each over MCP, the `axm` CLI and as a
DAG node. Successful provenance and storage results omit credential values. Errors and rejection reasons can contain unredacted exception text.

### `vault_doctor`

Returns value-free provenance in `ToolResult.data`, plus a `rejections` list
containing the `entry_point` and non-empty `reason` for every malformed
`axm.credentials` contribution skipped during discovery. The human-readable
`ToolResult.text` includes a `skipped contributions` line naming those entry
points (or `none`); any error is shaped into
`ToolResult(success=False, error=...)`. The catalog is loaded once and reused
for both provenance and rejection reporting.

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
| `group` | `str` | required | Credential group id |
| `name` | `str` | required | Spec name within the group |
| `value` | `str` | required | The value to store (never echoed back) |
| `instance` | `str \| None` | `None` | Multi-instance segment (keyring only) |

### `vault_delete`

`execute(*, group="", name="", instance=None)` looks up the catalog spec, then deletes only its keyring entry. Success returns `data={"deleted": "keyring:{group}.{name}"}`. The target text omits the instance even when an instance was selected. Unknown group/spec and backend failures become unsuccessful `ToolResult` objects.

This tool does not check sensitivity: deleting a CONFIG spec does not remove its TOML value. It also leaves environment overrides and rotation backups intact. `VaultDeleteTool` is discovered from `axm_vault.tools` but is not exported from the package root.

## Output and I/O boundaries

`vault_doctor.data` contains the provenance mapping **and** the reserved `rejections` list. Its `text` contains only `skipped contributions: ...`, not the provenance rows. Use `axm vault_doctor --json-output` for structured data; a text-only MCP façade may expose only that summary. The standalone `axm-vault doctor` prints provenance rows but does not print rejection details.

`doctor_data` probes backend availability even for an empty catalog. It does not call external authentication dependency `status()` methods: these are separate catalog capabilities consumed by `axm-doctor`. Instance enumeration delegates to provider code, which can perform I/O. An explicit instance is used only for groups marked `multi=True`; ordinary groups remain unsegmented. The probe never requests the prompt layer, but backend reads can still involve backend-specific interactions or failures.
