# Scaffold a Project

## Prerequisites

- Python ≥ 3.12
- [uv](https://github.com/astral-sh/uv) installed

## Steps

### 1. Create a new project

```bash
axm init_scaffold my-project \
  --org axm-protocols \
  --author "Your Name" \
  --email "you@example.com"
```

This scaffolds a production-grade Python project with:

- `pyproject.toml` (PEP 621, dynamic versioning via hatch-vcs)
- `src/` layout with `py.typed` marker
- Pre-configured linting (Ruff), typing (MyPy), testing (Pytest), and docs (MkDocs)
- CI/CD workflows (GitHub Actions)
- Automated commit-hook updates (weekly via `prek autoupdate`)
- Dependency groups: `dev`, `docs`

### 2. Required flags

| Flag | Short | Description |
|---|---|---|
| `--org` | | GitHub org or username |
| `--author` | | Author name |
| `--email` | | Author email |

### 3. Optional flags

| Flag | Short | Default | Description |
|---|---|---|---|
| `--name` | | *dir name* | Project name |
| `--license` | | `Apache-2.0` | License (MIT, Apache-2.0, EUPL-1.2) |
| `--license-holder` | | *--org* | License holder |
| `--description` | | | One-line description |
| `--private` / `--no-private` | | `True` | Keep the generated package private, or explicitly make it publishable |
| `--workspace` | | `False` | Scaffold a UV workspace instead |
| `--member` | | | Scaffold a member sub-package with this name |
| `--framework` | | `python` | `python`, `node`, `svelte`; use non-Python only for standalone projects |
| `--kind` | | | Scaffold kind: `standalone`, `workspace`, `member`, `paper`, `experiment`, `learning`, `protocol_unit`, `protocol` |
| `--profile` | | | Optional package profile; `protocols` is supported for Python |
| `--domain` | | | Protocol domain, required with `--profile protocols` |
| `--unit` | | | Protocol unit, required when declarations are supplied |
| `--protocols` | | | JSON list of action-only protocol payloads; `--domain` and `--unit` supply their shared identity |
| `--preview` | | `False` | Plan protocol files without changing the target |

### 4. Scaffold a workspace

```bash
axm init_scaffold my-workspace --workspace \
  --org myorg --author "Your Name" --email "you@example.com"
```

The `--workspace` flag generates a UV workspace with:

- Root `pyproject.toml` with `[tool.uv.workspace]` and `members = ["packages/*"]`
- Gold-standard root config: `dynamic = ["version"]` + hatch-vcs (git-tag driven,
  no static version to bump), the full ruff rule set (incl. `BLE`/`PLR`), and a
  `[tool.git-cliff]` changelog config. (mypy is configured per-package, not at the
  root.)
- Shared `Makefile` (`test`, `lint`, `type-check`, `docs-serve`, `docs-build`)
- `mkdocs.yml` with `monorepo` plugin
- CI workflow using `--package` matrix for per-member testing
- Commit-hook configuration, git-cliff settings, Dependabot, and GitHub Actions workflows

### 5. Scaffold a member package

From inside an existing workspace:

```bash
axm init_scaffold --member my-lib \
  --org myorg --author "Your Name" --email "you@example.com"
```

The `--member` flag:

1. Auto-detects the workspace root (walks up to find `[tool.uv.workspace]`)
2. Creates the package under `packages/my-lib/` using the member template
3. Patches root files: `Makefile`, `mkdocs.yml`, `pyproject.toml`, CI workflows

> **Note:** `--workspace` and `--member` are mutually exclusive.

### 6. Scaffold a public package

Standalone projects and workspace members are private by default: their
`pyproject.toml` contains the `Private :: Do Not Upload` classifier. This safe
default avoids an irreversible accidental PyPI publication.

Pass `--no-private` explicitly when the generated distribution is intended for
publication:

```bash
axm init_scaffold public-project --no-private \
  --org myorg --author "Your Name" --email "you@example.com"
```

The same option applies to a member scaffold:

```bash
axm init_scaffold --member public-lib --no-private \
  --org myorg --author "Your Name" --email "you@example.com"
```

In both cases, the generated classifier list keeps its development status,
Python versions, typing and license metadata, but omits
`Private :: Do Not Upload`.

### 7. Scaffold a standalone learning project

Use the learning kind for a fresh training or optimisation package:

```bash
axm init_scaffold learning-lab --kind learning \
  --org myorg --author "Your Name" --email "you@example.com"
```

The target contains `training.toml`, `study.toml`, a deterministic recipe at
`src/learning_lab/recipe.py`, the registered training tool at
`src/learning_lab/tools/train.py`, and
`tests_learning_lab/unit/test_recipe.py`. Its `pyproject.toml` declares the
learning domain under `[tool.axm-init.learning]` and registers the training
AXMTool under `[project.entry-points."axm.tools"]`.

`learning` is a standalone project kind. To apply the compatibility overlay to
an existing package, use the Python template API described in
[Template selection](../reference/templates.md#learning-project-and-compatibility-overlay).

### 8. Research and protocol scaffolds

- [Scaffold a paper and its experiments](scaffold-research.md)
- [Create, preview and apply protocol declarations](scaffold-protocols.md)
- [Scaffold Node or Svelte projects](scaffold-web.md)

### 9. Check PyPI availability

```bash
axm init_scaffold my-project --org myorg --author A --email e@e.com --check-pypi
```

The `--check-pypi` flag verifies the package name is available before scaffolding.

### 10. JSON output

```bash
axm init_scaffold my-project --org myorg --author A --email e@e.com --json-output
```

Outputs structured JSON for CI/automation use.

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `Missing required option --org` | Required flag not provided | Pass `--org`, `--author`, and `--email` explicitly |
| `--workspace and --member are mutually exclusive` | Both flags given | Use only one of `--workspace` or `--member` |
| `Not inside a UV workspace` | `--member` used outside workspace | Run from a workspace directory |
| `Member 'X' already exists` | Duplicate member name | Choose a different member name |
| `Name 'X' is not available on PyPI` | `--check-pypi` detected a taken name | Choose a different project name or drop `--check-pypi` |
| Existing destination content | Copier can encounter conflicts with existing files | Prefer a fresh destination and inspect the result before reusing one |
| `... is not a paper` | `--kind experiment` outside a detected paper | Scaffold the paper first (`--kind paper`), or point the path at the paper root |
| `Unknown --kind 'X'` | Kind outside the declared set | Use one of `standalone`, `workspace`, `member`, `paper`, `experiment`, `learning`, `protocol_unit`, `protocol` |
| `Copier template error` | Template engine failure (rare) | Ensure `copier` is installed: `uv pip install copier` |
