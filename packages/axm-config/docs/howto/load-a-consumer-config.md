# Load a consumer package's config

**Goal:** give your package a typed config object backed by `~/.axm`, with an
environment override for CI, in a few lines.

This is the pattern every `axm-config` consumer uses: declare a pydantic model,
call `load`, and let the resolver fill each field from `env > file > default`.

## 1. Declare a model

```python
from pydantic import BaseModel


class FredConfig(BaseModel):
    api_key: str          # required — ConfigError if unresolved
    timeout: int = 30     # optional — falls back to the model default
```

## 2. Load it under a namespace

```python
from axm_config import load

cfg = load("research.fred", FredConfig)
print(cfg.api_key, cfg.timeout)
```

`load` resolves each field by name: it looks for `api_key` then `timeout` in the
`research.fred` namespace, walking `env > file > default` for each. A required
field with no value anywhere raises `ConfigError`.

## 3. Seed the file layer

```bash
axm-config set research.fred api_key abc123
```

writes `[research.fred]` into `~/.axm/config.toml` (atomic, `0600`).

## 4. Override in CI with an environment variable

An environment variable always wins over the file. The variable name is
`AXM_<NS>_<KEY>`, upper-cased, with each namespace dot folded to a **double**
underscore:

```bash
AXM_RESEARCH__FRED_API_KEY=ci-secret python -m your_app   # wins over the file
```

## 5. Diagnose an unexpected value

If a field resolves to something you did not expect, ask the doctor where it
came from:

```bash
axm-config doctor research.fred
# research.fred.api_key: env      <- the env var is shadowing the file
```

or over MCP / the `axm` CLI:

```bash
axm config_doctor --namespace research.fred
```

The doctor is read-only: it reports the winning layer per key (`env` / `file` /
`default`) without reading the value into your process.
