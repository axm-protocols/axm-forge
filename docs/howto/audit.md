# Audit Your Project

Run a full quality audit against the AXM gold standard.

## Basic Usage

```bash
axm-init audit
```

Score your project out of 100 with a grade from **A** (≥90) to **F** (<40).

## Audit a Specific Path

```bash
axm-init audit /path/to/project
```

## Filter by Category

Run only one category of checks:

```bash
axm-init audit --category pyproject
axm-init audit --category ci
axm-init audit --category tooling
axm-init audit --category docs
axm-init audit --category structure
axm-init audit --category deps
axm-init audit --category changelog
```

## JSON Output for CI

```bash
axm-init audit --json
```

Use in CI to enforce quality gates:

```bash
axm-init audit --json | jq -e '.score >= 90'
```

## What Gets Checked (31 Checks)

| Category | Checks | Points |
|----------|--------|--------|
| **pyproject** | exists, urls, dynamic_version, mypy, ruff, pytest, coverage | 30 |
| **ci** | workflow, lint job, test job, security job, coverage upload | 15 |
| **tooling** | pre-commit (×5), Makefile targets | 15 |
| **docs** | mkdocs.yml, Diátaxis nav, plugins, gen_ref_pages, README | 15 |
| **structure** | src/ layout, py.typed, tests/, CONTRIBUTING, LICENSE | 15 |
| **deps** | dev group, docs group | 5 |
| **changelog** | git-cliff config, no manual CHANGELOG | 5 |

## Reading the Report

Each failed check includes:

- **Problem**: What's wrong
- **Details**: Specific missing items
- **Fix**: Actionable remediation step

Example:

```
❌ docs.readme (3 pts)
   Problem: README missing 1 section(s)
   Missing: Development
   Fix:     Add Development section(s) to README.md.
```
