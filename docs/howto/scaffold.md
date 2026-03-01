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
- Automated pre-commit hook updates (weekly via `pre-commit autoupdate`)
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

### 4. Check PyPI availability

```bash
axm-init scaffold my-project --org myorg --author A --email e@e.com --check-pypi
```

The `--check-pypi` flag verifies the package name is available before scaffolding.

### 5. JSON output

```bash
axm-init scaffold my-project --org myorg --author A --email e@e.com --json
```

Outputs structured JSON for CI/automation use.

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `Missing required option --org` | Required flag not provided | Pass `--org`, `--author`, and `--email` explicitly |
| `Name 'X' is not available on PyPI` | `--check-pypi` detected a taken name | Choose a different project name or drop `--check-pypi` |
| `Target directory already exists` | Non-empty destination directory | Use an empty directory or remove existing files first |
| `Copier template error` | Template engine failure (rare) | Ensure `copier` is installed: `uv pip install copier` |
