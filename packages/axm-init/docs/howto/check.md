# Check Your Project

Run a full quality check against the AXM gold standard.

## Basic Usage

```bash
axm init_check
```

Score your project out of 100 with a grade from **A** (≥90) to **F** (<40).

## Check a Specific Path

```bash
axm init_check /path/to/project
```

## Filter by Category

Run only one category of checks:

```bash
axm init_check --category pyproject
axm init_check --category ci
axm init_check --category tooling
axm init_check --category docs
axm init_check --category structure
axm init_check --category deps
axm init_check --category changelog
axm init_check --category workspace
```

## JSON Output for CI

```bash
axm init_check --json-output
```

Use in CI to enforce quality gates:

```bash
report=$(mktemp)
trap 'rm -f "$report"' EXIT
status=0
axm init_check --json-output > "$report" || status=$?
if [ "$status" -gt 1 ]; then exit "$status"; fi
jq -e 'has("score") and (.score != null) and (.score >= 90)' "$report"
```

This example intentionally accepts an applicable score of at least 90, even
though the tool exits 1 below 100. Invalid/missing JSON and N/A fail this gate.
For the built-in 100-point policy, use the tool's exit status directly.

## Agent Output for AI

```bash
axm init_check --agent
```

Returns compact JSON optimized for AI agents: passed checks are summarized in one line, failed checks include full detail with fix hints.

## Verbose Output

```bash
axm init_check --verbose
```

Shows every individual check with its status and weight:

```
pyproject (29/29)
    ✅ pyproject.pyproject_exists       4/4  pyproject.toml found
    ✅ pyproject.pyproject_urls          3/3  All 4 URLs present
    ✅ pyproject.pyproject_dynamic_version  3/3  Dynamic version with hatch-vcs
    ...
```

By default, only failures are displayed.

## What Gets Checked

| Category | Checks | Points |
|----------|--------|--------|
| **pyproject** | exists, urls, dynamic_version, mypy, ruff, pytest, coverage, classifiers, ruff_rules, wheel_doc_shipping | 29 |
| **ci** | workflow, lint job, test job, security job, trusted publishing, dependabot | 16 |
| **tooling** | commit-hook config (×5), hooks installed, Makefile targets | 16 |
| **docs** | mkdocs.yml, Diátaxis nav, plugins, gen_ref_pages, README, README badges, standalone API wiring | 18 |
| **structure** | src/ layout, py.typed, tests/, CONTRIBUTING, LICENSE, uv.lock, .python-version | 17 |
| **deps** | dev group, docs group | 5 |
| **changelog** | git-cliff config, no manual CHANGELOG | 5 |
| **workspace** | packages layout, members consistent, monorepo plugin, matrix packages, requires-python compat, root name collision, pytest importmode, pytest testpaths, quality workflow, unique test-suite directory names | 21 |

| **paper** | paper structure, plan, research protocol | 15 |
| **experiment** | directory structure and required files | 10 |

These are the Python catalogue categories before context filtering.
See the [complete catalogue](../reference/checks/catalogue.md) for canonical
identifiers and Node/React/Svelte selection.

### Workspace Context

`axm init_check` detects standalone, workspace, member, paper or experiment
contexts. Members redirect CI and shared tooling checks to their workspace
root; other inapplicable checks are skipped. Per-package exclusions use
`[tool.axm-init].exclude`. See [context routing](../explanation/project-contexts.md).

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

Projects scaffolded with `axm init_scaffold` include an automated **check badge** powered by GitHub Actions. The badge displays your check score and updates on every push to `main`.

### How It Works

1. **Push to `main`** triggers `.github/workflows/axm-quality.yml`
2. The workflow runs `axm init_check --json-output` and extracts the score
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

If your project wasn't scaffolded with `axm init_scaffold`, you can add the badge manually:

1. Copy the workflow from any scaffolded project (`.github/workflows/axm-quality.yml`)
2. Add the badge markup to your README
3. Push to `main` — the badge appears after the first workflow run

!!! tip "First run"
    The badge will show "resource not found" until the first workflow run pushes `axm-init.json` to `gh-pages`. Just push to `main` and wait for the action to complete.
