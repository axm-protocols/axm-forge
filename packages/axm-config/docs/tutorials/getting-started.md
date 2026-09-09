# Getting started

Follow one non-sensitive value through the file, environment and default layers.

## Install and verify

Use Python 3.12 or later:

```bash
uv add axm-config
axm-config --help
python -c 'from importlib.metadata import version; print(version("axm-config"))'
```

There is no root `axm_config.__version__` export. Read the installed distribution
version with `importlib.metadata`.

## Persist a setting in a separate profile

Choose an unused profile name. This example creates
`~/.axm/profiles/docs-demo/config.toml`; it does not use the production file.

```bash
AXM_PROFILE=docs-demo axm-config set research.demo timeout 30
AXM_PROFILE=docs-demo axm-config get research.demo timeout
# 30
AXM_PROFILE=docs-demo axm-config doctor research.demo
# research.demo.timeout: file
```

The CLI writes the string `"30"`. For native TOML types, use `set_` in Python;
the [consumer guide](../howto/load-a-consumer-config.md) shows typed model loading.

## Override for one command

```bash
AXM_PROFILE=docs-demo AXM_RESEARCH__DEMO_TIMEOUT=10 axm-config get research.demo timeout
# 10
AXM_PROFILE=docs-demo AXM_RESEARCH__DEMO_TIMEOUT=10 axm-config doctor research.demo
# research.demo.timeout: env
```

Dots in the namespace become double underscores; key underscores stay single.
The override is scoped to the command and does not rewrite the file.

## Remove the value

```bash
AXM_PROFILE=docs-demo axm-config delete research.demo timeout
AXM_PROFILE=docs-demo axm-config get research.demo timeout
# None
```

The CLI has no default argument: an unresolved value prints `None` and succeeds.
Python callers can use `get("research.demo", "timeout", default=30)`.
The profile directory can remain after deleting its last setting.

## Continue

Read the [profile guide](../howto/profiles.md) before treating a profile as an
isolation boundary, and the [persistence limits](../explanation/architecture.md)
before sharing a file among writers. For passwords and tokens, use axm-vault.
