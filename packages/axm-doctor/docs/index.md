# axm-doctor

Detect an environment, inspect a proposed repair, then explicitly apply it.
Doctor provides tool and authentication status, credential provenance,
install plans and delegation to axm-vault setup.

Start with the [tutorial](tutorials/getting-started.md), then choose a task:

- [Preflight an agent or DAG](howto/preflight.md)
- [Bootstrap a machine](howto/bootstrap.md)
- [Inspect the CLI and exit codes](reference/cli.md)
- [Use the Python contracts](reference/python.md)
- [Inspect generated API documentation](reference/api.md)
- [Understand ownership and current limits](explanation/architecture.md)

```bash
uv add axm-doctor
uv run axm-doctor check
```

This command reports without installing or prompting. It can invoke local
binaries and installed provider probes. Normal completion exits 0 even when
components are missing; use `--strict` for the built-in CI policy.

The two request–response tools, `env_doctor` and `auth_status`, return
structured observations. Their `success` flag means report generation
succeeded, not that every observed component is ready.
