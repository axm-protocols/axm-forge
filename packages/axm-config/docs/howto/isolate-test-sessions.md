# Isolate test sessions

When axm-config is installed in a test environment, every pytest session is
already sandboxed: the six AXM state paths (`sessions_root()`, `quality_dir()`,
`protocols_dir()`, `tickets_db()`, `warden_socket()`, `warden_log_path()`)
resolve under a temporary root instead of `~/axm` or `~/.axm`. You do not need
to edit any test or `conftest.py`.

## Check that a session is sandboxed

```python
from axm_config import sessions_root
from axm_config.sandbox import active_sandbox


def test_writes_stay_in_the_sandbox() -> None:
    sandbox = active_sandbox()
    assert sandbox is not None
    assert sessions_root().is_relative_to(sandbox.root)
```

The root is created when the session starts and deleted when it ends. The pytest
header lists `axm-config` under `plugins:` when the plugin is loaded.

## Subprocesses

The sandbox is stored in `AXM_SANDBOX_*` environment variables. A CLI,
`python -c` or daemon started by a test inherits them and resolves the same
paths, with the profile that was active when pytest started.

## When a session refuses to start

If one of the six override variables (for example `AXM_TICKETS_DB_PATH` or
`AXM_PATHS_SESSIONS_ROOT`) points at or below `~/axm` or `~/.axm` when pytest
starts, the session stops before collecting any test and the error names the
variable. Unset that variable, or point it at a temporary directory.

## Use a different layout in one test

A test that sets `AXM_PROFILE` or `HOME`, or one of the six override variables,
or a new `AXM_HOME` whose `config.toml` sets the key, takes precedence over the
sandbox for the affected keys. The order is in the
[resolution precedence](../reference/sandbox.md#resolution-precedence).

## Opt out

Disable the plugin for one run with `pytest -p no:axm_config`, or disable all
entry-point plugins with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`. Either way the
tests then resolve the real state paths.
