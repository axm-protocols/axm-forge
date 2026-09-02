---
hide:
  - navigation
  - toc
---

# axm-config

<p align="center">
  <strong>Non-sensitive runtime config under ~/.axm (env>file>default)</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml">
    <img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI" />
  </a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-config/axm-init.json" alt="axm-init" />
  </a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-config/axm-audit.json" alt="axm-audit" />
  </a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-config/coverage.json" alt="Coverage" />
  </a>
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" />
</p>

---

## Installation

```bash
uv add axm-config
```

## Quick Start

The public API exposes the generic `get`, `load`, `set_`, and `delete`
resolver, typed accessors for shared runtime settings, and the state-profile
transport helpers. In particular, `inference_base_url()`, `inference_model()`,
and `inference_origin()` centralise the local inference endpoint, model
identifier, and provider origin.

```python
from axm_config import (
    ConfigError,
    axm_home,
    current_profile,
    profile_config_path,
    profile_env,
    profile_root,
    delete,
    get,
    inference_base_url,
    inference_model,
    inference_origin,
    load,
    set_,
)

# Resolve (and create, 0700) the per-user ~/.axm directory.
home = axm_home()
print(home)  # e.g. /Users/you/.axm

# With AXM_PROFILE=dev, resolve the isolated state contract and propagate it
# to a child process. Unset or empty AXM_PROFILE keeps production unchanged.
profile = current_profile()  # dev
root = profile_root()  # ~/.axm/profiles/dev
config_file = profile_config_path()  # ~/.axm/profiles/dev/config.toml
child_env_overlay = profile_env()  # {"AXM_PROFILE": "dev"}

# Resolve local inference settings. AXM_INFERENCE_BASE_URL and
# AXM_INFERENCE_MODEL override these defaults without rewriting either value.
# AXM_INFERENCE_ORIGIN selects anthropic, openai, google, or local; unknown
# values raise ConfigError at the configuration boundary.
base_url = inference_base_url()  # http://127.0.0.1:8000/v1
model = inference_model()  # ornith-ai/Ornith-1.5-9B-MLX-4bit
origin = inference_origin()  # local

# Resolve runtime config with env > file > default precedence.
set_("research.fred", "api_key", "abc123")  # writes [research.fred] in ~/.axm/config.toml
key = get("research.fred", "api_key", default=None)  # "abc123"

# Remove a key (no-op if absent); it then resolves to the default again.
delete("research.fred", "api_key")  # set_(..., None) does the same
get("research.fred", "api_key", default="fallback")  # "fallback"

# namespace/key are validated: a traversal/empty/invalid segment raises
# ConfigError and never writes outside ~/.axm.
set_("../evil", "k", "v")  # raises ConfigError

# Env wins: AXM_RESEARCH__FRED_API_KEY overrides the file value.
# (a namespace dot folds to a *double* underscore so a dotted namespace
#  stays distinct from an underscore one; keys must be dot-free.)
# Populate a pydantic model — each field is resolved by name.
from pydantic import BaseModel

class FredConfig(BaseModel):
    api_key: str
    timeout: int = 30

cfg = load("research.fred", FredConfig)  # ConfigError if api_key unresolved
```

From the shell, the `axm-config` command exposes the same resolution layer:

```bash
axm-config set research.fred api_key abc123  # persist to ~/.axm
axm-config get research.fred api_key         # prints the resolved value
axm-config delete research.fred api_key      # remove a key (no-op if absent)
axm-config path                              # prints the ~/.axm home
axm-config doctor research.fred              # per-key provenance, read-only
```

## Features

- ✅ **`~/.axm` home** — `axm_home()` resolves and creates the per-user
  config directory with mode `0700` (idempotent, tightens looser perms)
- ✅ **State-profile transport** — `current_profile()` reads `AXM_PROFILE`,
  defaulting unset or empty values to `production`, and validates names
  lexically against `^[a-z][a-z0-9-]{0,31}$`. A non-production profile such
  as `dev` resolves to `~/.axm/profiles/dev` and its `config.toml` through
  `profile_root()` / `profile_config_path()`; `profile_env()` returns the
  environment overlay to propagate the active profile to a child process.
  These helpers define the transport contract only: the existing resolver
  and `NamespaceStore` continue to use the production store until their
  consumers explicitly adopt profile routing
- ✅ **Layered resolution** — `get()` / `set_()` / `delete()` resolve a
  `(namespace, key)` with `env > file > default` precedence; the env name is
  derived deterministically as `AXM_<NS>_<KEY>` (upper-cased, each namespace
  dot → a *double* underscore). The mapping is **provably injective** and
  always POSIX-valid: segments are lowercase-only (so `Demo` and `demo` can
  never fold to the same `AXM_DEMO_*`), a namespace carries no `_` of its own
  and no `-`, and a key joins lowercase-alphanumeric runs with **single** `_`
  (no leading/trailing/doubled `__`) — so a `__` can only come from a
  namespace dot, the lone single `_` separates the folded namespace from the
  key, and no `-` ever leaks into the name. The on-disk store keeps **one**
  `~/.axm/config.toml` with a `[<namespace>]` table per namespace (a dotted
  namespace → a nested table, e.g. `[storage.portfolio]`) and writes it
  atomically (file `0600`, temp file cleaned up even if the atomic move
  fails). A read-modify-write of the whole file preserves every other
  namespace's section; a missing or corrupt file/section degrades gracefully
  to `{}` instead of raising. Legacy per-namespace `~/.axm/<ns>.toml` files
  (the previous layout) are read-through and folded into `config.toml` on the
  next write — no silent data loss. `delete()` removes a key (no-op if
  absent); `set_(ns, key, None)` routes to the same delete
- ✅ **Path-traversal safe & unambiguous env names** — `namespace` and `key`
  are validated at the public boundary against safe-segment patterns (a
  namespace is lowercase-alphanumeric segments joined by dots,
  `^[a-z0-9]+(\.[a-z0-9]+)*$`, so uppercase, `_` and `-` in a namespace are
  rejected; a key is lowercase-alphanumeric segments joined by single `_`,
  `^[a-z0-9]+(_[a-z0-9]+)*$`, so uppercase, dots/dashes, and leading/trailing
  or doubled `_` in a key are rejected). A traversal/empty/invalid segment
  raises `ConfigError`, a config file can never land outside the resolved
  `~/.axm` home (a `HOME` pointing into a git checkout is refused), and the
  derived env-var name is always POSIX-valid
- ✅ **Typed inference settings** — `inference_base_url()`,
  `inference_model()`, and `inference_origin()` resolve the `[inference]`
  `base_url`, `model`, and `origin` keys with stable local defaults. Address and
  model strings are returned verbatim; origin is constrained to `anthropic`,
  `openai`, `google`, or `local`, and an unsupported value raises `ConfigError`
- ✅ **Model binding** — `load(namespace, model)` populates a consumer's
  pydantic model, resolving each field by name; a missing required field
  raises `ConfigError`
- ✅ **`axm-config` CLI** — `get` / `set` / `delete` / `path` / `doctor`
  subcommands wrap the resolution layer for shell use; every command delegates
  to the same central function with no logic duplicated
- ✅ **Provenance doctor** — the `config_doctor` AXMTool reports which layer
  (`env` / `file` / `default`) would win for every visible key, read-only;
  available over MCP, the `axm` CLI, and `axm-config doctor`
- ✅ **Minimal deps** — stdlib `pathlib` / `os` / `tomllib`, plus `tomli-w`
  for atomic TOML writes and `cyclopts` for the CLI
- ✅ **Modern Python** — 3.12+ with strict typing

---

<div style="text-align: center; margin: 2rem 0;">
  <a href="tutorials/getting-started/" class="md-button md-button--primary">Get Started →</a>
  <a href="reference/cli/" class="md-button">Reference</a>
</div>
