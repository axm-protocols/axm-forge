# Getting Started

This tutorial walks you through installing `axm-doctor` and using it to check —
and repair — a development environment. By the end you will have run the
read-only report, inspected a tool's status from Python, and seen a dry-run
install plan for an absent tool.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
uv add axm-doctor
```

Or with pip:

```bash
pip install axm-doctor
```

## Step 1: Run the read-only report

`axm-doctor check` prints one tab-separated row per probed tool, per
third-party auth state, and per missing secret. It **installs nothing and
prompts for nothing**, and always exits `0` — safe to run anywhere.

```console
$ axm-doctor check
tool	uv	present	0.9.18
tool	gh	present	2.87.3
tool	codex	absent	-
auth	gh	logged_in	-
auth	claude	logged_out	claude login
secret	research.fred.api_key	axm-vault set research.fred.api_key
```

Read it top to bottom: `uv` and `gh` are present (with their versions),
`codex` is absent, `claude` is logged out (with the command to recover), and
one vault secret is missing (with its setup hint).

## Step 2: Query a single tool from Python

Every row above is backed by a function you can call directly. Detection is
read-only and never reads a token or version banner it does not need.

```python
from axm_doctor import detect_tool, detect_auth

detect_tool("uv")      # ToolStatus(name='uv', state='present', version='0.9.18', path=...)
detect_auth("claude")  # AuthStatus(tool='claude', state='logged_out', login_cmd='claude login')
```

## Step 3: See an install plan (dry-run)

For an absent tool, ask for its **official** install command. Building a plan
runs nothing; `run_install` is a dry-run by default and only echoes the command
it *would* run.

```python
from axm_doctor import install_command, run_install

plan = install_command("uv")     # InstallPlan(human_command='curl -LsSf https://astral.sh/uv/install.sh | sh', ...)
run_install(plan)                # InstallResult(executed=False, ...) — nothing installed
```

Passing `confirm=True` (or answering `y` to the CLI prompt) is the only way a
system change happens.

## Step 4: Repair interactively

`axm-doctor bootstrap` is the interactive path: for each absent tool it offers
the install command; for each missing secret it offers to run vault setup.
Nothing happens without an explicit `y`.

```console
$ axm-doctor bootstrap
codex is absent. Install command: npm i -g @openai/codex
install codex? [y/N] n
  skipped: npm i -g @openai/codex
```

## Next Steps

- [CLI Reference](../reference/cli.md) — the full `check` / `bootstrap` contract
- [Architecture](../explanation/architecture.md) — detect → propose → orchestrate
  and the three invariants
- [How-To Guides](../howto/index.md) — task recipes (agent preflight, new-machine
  bootstrap, `env_doctor` in a loom graph)
