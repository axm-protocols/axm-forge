# Provide a credential without a terminal

`axm-doctor bootstrap` and `provision_missing(confirm=True)` both need a human
at a TTY: without one, confirmed provisioning refuses and returns a reason.
When the caller already holds the value — a cockpit behind a web server, a
packaged application with no shell, an installer — use `provide_secret`
instead. It never reads `sys.stdin`.

## Write one value

```python
from axm_doctor import missing_secrets, provide_secret

row = missing_secrets()[0]
result = provide_secret(
    group=row.group,
    name=row.name,
    value=caller_supplied_token,
    instance=row.instance,
)
if not result.stored:
    raise RuntimeError(result.reason)
```

Take the coordinates from `missing_secrets()` rather than typing them by hand;
`instance` designates the account inside a multi-instance group and stays None
elsewhere. On success `result.target` is vault's destination, prefixed
`keyring:` or `config:`.

## Trust the re-scan, not the absence of an exception

`stored=True` does not mean "the write call returned". Doctor re-resolves the
vault catalog after the write and reports success only when the coordinate no
longer appears as missing. A backend that accepted the write and kept nothing
therefore yields `stored=False`, with the coordinate in `still_missing` and
named in `reason`. Surface `reason`; do not assume a silent success and do not
re-send the value blindly.

`still_missing` also answers "what is left?" without a second census: it lists
the account-aware coordinates still unresolved after the call.

## Sensitivities you can and cannot write

Routing belongs to vault, not to doctor:

| Declared sensitivity | Outcome |
| --- | --- |
| SECRET | stored in the OS keyring; `target` prefixed `keyring:` |
| CONFIG | stored through axm-config; `target` prefixed `config:` |
| NONSENSITIVE | refused; `reason` names the environment-only rule |

A refused NONSENSITIVE credential is not a transient failure to retry: it is
declared environment-only, so set its environment variable instead of creating
a second, stale source of truth. An unknown group or credential name is
reported the same way — `stored=False` with vault's message as `reason`.

## Keep the value out of your logs

`ProvideResult` declares no field able to hold the value, and the call emits no
log record containing it. Everything after the call is yours to keep clean:
report `result.reason` and the coordinates, never `value`.

The exact fields are in
[Python contracts](../reference/python.md#caller-supplied-credential-values).
