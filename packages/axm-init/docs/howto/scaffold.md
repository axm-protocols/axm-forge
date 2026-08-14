# Scaffold a Project

## Prerequisites

- Python ≥ 3.12
- [uv](https://github.com/astral-sh/uv) installed

## Steps

### 1. Create a new project

```bash
axm-init scaffold my-project \
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
| `--org` | `-o` | GitHub org or username |
| `--author` | `-a` | Author name |
| `--email` | `-e` | Author email |

### 3. Optional flags

| Flag | Short | Default | Description |
|---|---|---|---|
| `--name` | `-n` | *dir name* | Project name |
| `--license` | `-l` | `Apache-2.0` | License (MIT, Apache-2.0, EUPL-1.2) |
| `--license-holder` | | *--org* | License holder |
| `--description` | `-d` | | One-line description |
| `--workspace` | `-w` | `False` | Scaffold a UV workspace instead |
| `--member` | `-m` | | Scaffold a member sub-package with this name |
| `--kind` | `-k` | | Scaffold kind: `standalone`, `workspace`, `member`, `paper`, `experiment` |

### 4. Scaffold a workspace

```bash
axm-init scaffold my-workspace --workspace \\
  --org myorg --author "Your Name" --email "you@example.com"
```

The `--workspace` flag generates a UV workspace with:

- Root `pyproject.toml` with `[tool.uv.workspace]` and `members = ["packages/*"]`
- Gold-standard root config: `dynamic = ["version"]` + hatch-vcs (git-tag driven,
  no static version to bump), the full ruff rule set (incl. `BLE`/`PLR`), and a
  `[tool.git-cliff]` changelog config. (mypy is configured per-package, not at the
  root.)
- Shared `Makefile` (`test-all`, `lint-all`, `docs-serve`)
- `mkdocs.yml` with `monorepo` plugin
- CI workflow using `--package` matrix for per-member testing
- Pre-commit, cliff.toml, dependabot, and 6 GitHub Actions workflows

### 5. Scaffold a member package

From inside an existing workspace:

```bash
axm-init scaffold --member my-lib \\
  --org myorg --author "Your Name" --email "you@example.com"
```

The `--member` flag:

1. Auto-detects the workspace root (walks up to find `[tool.uv.workspace]`)
2. Creates the package under `packages/my-lib/` using the member template
3. Patches root files: `Makefile`, `mkdocs.yml`, `pyproject.toml`, CI workflows

> **Note:** `--workspace` and `--member` are mutually exclusive.

### 6. Scaffold a paper

```bash
axm-init scaffold my-paper --kind paper \\
  --org myorg --author "Your Name" --email "you@example.com" \\
  --description "Attention study"
```

The `paper` kind renders the paper submodule:

- `PLAN.md` — the paper plan
- `PIPELINE.md` — where the data cohort comes from, what it covers and the
  command that reproduces it (skeleton to fill in; `paper.paper_structure`
  fails while it is absent)
- `README.md`
- `paper/` — `main.tex`, `references.bib` and its `Makefile`
- `experiments/` — the root every experiment lands in
- `pyproject.toml` carrying `[tool.axm-lab]`, the marker that makes the
  directory a *detected paper*

### 7. Scaffold an experiment inside a paper

```bash
axm-init scaffold my-paper --kind experiment --name baseline \\
  --org myorg --author "Your Name" --email "you@example.com"
```

The `experiment` kind:

1. Refuses any target that is not a detected paper — it fails **before writing
   anything**, so a mistyped path never leaves debris
2. Names the directory itself, with the next free zero-padded index and the
   slugified `--name`: `experiments/01-baseline/`, then `experiments/02-…`
3. Renders the experiment scaffold flat inside it — `manifest.yaml` (the 1.0.0
   experiment contract, complete before any script runs), `inputs/`, `scripts/`,
   `outputs/`, `analysis/analysis.md` and `figures/figures.yaml`

> **Note:** `figures/figures.yaml` is the figure declaration the experiment
> contract reads — it ships as an empty declaration with a commented skeleton
> naming the `id`, `caption`, `script` and `reads` keys. `analysis/analysis.md`
> is the end-of-experiment reading, filled once the outputs exist; the metrics
> file beside it (`analysis/metrics.yaml`) is emitted by the run, never
> scaffolded.

> **Note:** the index belongs to the tool, never to the template — re-running
> the command always allocates the next free slot.

### 8. Check PyPI availability

```bash
axm-init scaffold my-project --org myorg --author A --email e@e.com --check-pypi
```

The `--check-pypi` flag verifies the package name is available before scaffolding.

### 9. JSON output

```bash
axm-init scaffold my-project --org myorg --author A --email e@e.com --json
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
| `Target directory already exists` | Non-empty destination directory | Use an empty directory or remove existing files first |
| `... is not a paper` | `--kind experiment` outside a detected paper | Scaffold the paper first (`--kind paper`), or point the path at the paper root |
| `Unknown --kind 'X'` | Kind outside the declared set | Use one of `standalone`, `workspace`, `member`, `paper`, `experiment` |
| `Copier template error` | Template engine failure (rare) | Ensure `copier` is installed: `uv pip install copier` |
