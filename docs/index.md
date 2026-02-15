---
hide:
  - navigation
  - toc
---

# axm

<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-init/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>AXM CLI — Unified command-line interface for the AXM ecosystem.</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm/actions/workflows/ci.yml">
    <img src="https://github.com/axm-protocols/axm/actions/workflows/ci.yml/badge.svg" alt="CI" />
  </a>
  <a href="https://axm-protocols.github.io/axm-init/explanation/check-grades/">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm/gh-pages/badges/axm-init.json" alt="axm-init" />
  </a>
  <a href="https://axm-protocols.github.io/axm-audit/">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm/gh-pages/badges/axm-audit.json" alt="axm-audit" />
  </a>
  <a href="https://coveralls.io/github/axm-protocols/axm">
    <img src="https://coveralls.io/repos/github/axm-protocols/axm/badge.svg?branch=main" alt="Coverage" />
  </a>
  <a href="https://pypi.org/project/axm/">
    <img src="https://img.shields.io/pypi/v/axm" alt="PyPI" />
  </a>
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" />
  <a href="https://axm-protocols.github.io/axm/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs" /></a>
</p>

---

## Install

=== "uv"

    ```bash
    uv add axm              # CLI shell only
    uv add axm[init]        # + scaffolding & project checks
    uv add axm[audit]       # + code quality audits
    uv add axm[all]         # entire ecosystem
    ```

=== "pip"

    ```bash
    pip install axm              # CLI shell only
    pip install axm[init]        # + scaffolding & project checks
    pip install axm[audit]       # + code quality audits
    pip install axm[all]         # entire ecosystem
    ```

## Quick Start

```bash
axm                          # list available commands
axm init_scaffold my-project # scaffold a new project (requires axm[init])
axm init_check .             # check conformity (requires axm[init])
axm audit .                  # audit code quality (requires axm[audit])
```

## How It Works

`axm` is a **thin autodiscovery wrapper** (~80 lines). It finds commands from installed AXM packages via [`importlib.metadata.entry_points`](https://docs.python.org/3/library/importlib.metadata.html#entry-points) and registers them as subcommands.

No plugins installed? `axm` tells you what to install.

---

<div style="text-align: center; margin: 2rem 0;">
  <a href="tutorials/getting-started/" class="md-button md-button--primary">Get Started →</a>
  <a href="explanation/architecture/" class="md-button">Architecture</a>
</div>
