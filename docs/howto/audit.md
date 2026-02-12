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

## What Gets Checked (38 Checks)

| Category | Checks | Points |
|----------|--------|--------|
| **pyproject** | exists, urls, dynamic_version, mypy, ruff, pytest, coverage, classifiers, ruff_rules | 27 |
| **ci** | workflow, lint job, test job, security job, coverage upload, trusted publishing, dependabot | 18 |
| **tooling** | pre-commit (×5), Makefile targets | 14 |
| **docs** | mkdocs.yml, Diátaxis nav, plugins, gen_ref_pages, README | 14 |
| **structure** | src/ layout, py.typed, tests/, CONTRIBUTING, LICENSE, uv.lock, .python-version | 17 |
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

## CI Badge

Projects scaffolded with `axm-init init` include an automated **audit badge** powered by GitHub Actions. The badge displays your audit score and updates on every push to `main`.

### How It Works

1. **Push to `main`** triggers `.github/workflows/axm-init.yml`
2. The workflow runs `axm-init audit --json` and extracts the score
3. A shields.io JSON badge is generated and pushed to `gh-pages`
4. Your README displays the score via a shields.io endpoint badge

### Badge in Your README

The scaffolded README already includes the badge. It looks like this:

```html
<a href="https://your-org.github.io/your-project/">
  <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/your-org/your-project/gh-pages/badges/axm-init.json" alt="axm-init">
</a>
```

### Adding to an Existing Project

If your project wasn't scaffolded with `axm-init init`, you can add the badge manually:

1. Copy the workflow from any scaffolded project (`.github/workflows/axm-init.yml`)
2. Add the badge markup to your README
3. Push to `main` — the badge appears after the first workflow run

!!! tip "First run"
    The badge will show "resource not found" until the first workflow run pushes `axm-init.json` to `gh-pages`. Just push to `main` and wait for the action to complete.
