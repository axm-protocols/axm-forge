# axm-config

Non-sensitive runtime config under ~/.axm (env>file>default)

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-config/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-config/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-config/coverage.json" alt="Coverage"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
</p>

---

## Overview

Non-sensitive runtime config under ~/.axm (env>file>default)

## Features

- 🏠 **`~/.axm` home** — `axm_home()` resolves and creates the per-user config
  directory `0700` (idempotent, tightens looser perms)
- 🧭 **Layered resolution** — `get` / `set_` / `delete` resolve a
  `(namespace, key)` with `env > file > default` precedence; the env name is
  derived deterministically as `AXM_<NS>_<KEY>` (upper-cased, each namespace dot
  → a *double* underscore). The mapping is provably injective and POSIX-valid
- 🗄️ **Single-file store** — one atomic `~/.axm/config.toml` (`0600`) with a
  `[namespace]` table per namespace; a read-modify-write preserves every other
  section, an absent/corrupt file degrades to `{}`, and legacy per-namespace
  files are folded in on the next write
- 🛡️ **Path-traversal safe** — `namespace`/`key` are validated at every public
  boundary (lowercase-only patterns; traversal/empty/NUL raise `ConfigError`),
  and a `HOME` resolving inside a git checkout is refused as `UnsafeHomeError`
- 🧬 **Model binding** — `load(namespace, model)` populates a pydantic model,
  resolving each field by name; a missing required field raises `ConfigError`
- 🩺 **Provenance doctor** — the `config_doctor` AXMTool reports which layer
  (`env` / `file` / `default`) wins per visible key, read-only; over MCP, the
  `axm` CLI, and `axm-config doctor`
- 🖥️ **`axm-config` CLI** — `get` / `set` / `delete` / `path` / `doctor`
  wrap the same central resolution layer for shell use

## Installation

```bash
uv add axm-config
```

Or as a workspace dependency in `pyproject.toml`:

```toml
[project]
dependencies = ["axm-config"]

[tool.uv.sources]
axm-config = { workspace = true }
```

## Development

This package is part of the [**axm-forge**](https://github.com/axm-protocols/axm-forge) workspace.

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-groups
uv run --package axm-config --directory packages/axm-config pytest -x -q
```

## License

Apache-2.0 — © 2026 Gabriel Jarry
