# CI Badge

Add an `axm-audit` quality badge to your project.

## Quick Setup

### 1. Create the workflow

Add `.github/workflows/axm-audit.yml`:

```yaml
name: axm-audit quality

on:
  push:
    branches: [main]

permissions:
  contents: write

jobs:
  audit:
    name: AXM Audit & Badge
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0
      - uses: astral-sh/setup-uv@v7
      - run: uv python install 3.12

      - name: Run AXM Audit
        id: audit
        run: |
          RESULT=$(uvx axm-audit audit . --json) || true
          SCORE=$(echo "$RESULT" | jq '.score')
          GRADE=$(echo "$RESULT" | jq -r '.grade')
          echo "score=$SCORE" >> "$GITHUB_OUTPUT"
          echo "grade=$GRADE" >> "$GITHUB_OUTPUT"
          echo "📋 AXM Audit: Score $SCORE/100 — Grade $GRADE"

      - name: Choose badge color
        id: color
        run: |
          SCORE=$(echo "${{ steps.audit.outputs.score }}" | cut -d. -f1)
          if [ "$SCORE" -ge 95 ]; then COLOR="brightgreen"
          elif [ "$SCORE" -ge 80 ]; then COLOR="green"
          elif [ "$SCORE" -ge 60 ]; then COLOR="yellow"
          else COLOR="red"; fi
          echo "color=$COLOR" >> "$GITHUB_OUTPUT"

      - name: Generate badge JSON
        run: |
          mkdir -p badges
          jq -n \
            --arg score "${{ steps.audit.outputs.score }}" \
            --arg color "${{ steps.color.outputs.color }}" \
            '{
              schemaVersion: 1,
              label: "axm-audit",
              message: "\($score)%",
              color: $color,
              style: "flat"
            }' > badges/axm-audit.json

      - name: Push badge to gh-pages
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_branch: gh-pages
          publish_dir: ./badges
          destination_dir: badges
          keep_files: true
          commit_message: "badge: update axm-audit score"
```

!!! note "uvx vs uv run"
    Use `uvx axm-audit` for external projects (installs from PyPI).
    Within the axm-audit repo itself, we use `uv run axm-audit` (local lib).

### 2. Add the badge to your README

```markdown
[![axm-audit](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/YOUR_ORG/YOUR_REPO/gh-pages/badges/axm-audit.json)](https://github.com/YOUR_ORG/YOUR_REPO/actions/workflows/axm-audit.yml)
```

### 3. Push to main

The badge will appear after the first workflow run pushes to `gh-pages`.

## Color Thresholds

| Score | Color |
|---|---|
| ≥ 95 | 🟢 `brightgreen` |
| ≥ 80 | 🟢 `green` |
| ≥ 60 | 🟡 `yellow` |
| < 60 | 🔴 `red` |

## Score Components

The badge shows the [composite quality score](../explanation/scoring.md) — a weighted average of linting, type safety, complexity, security, dependencies, and testing (0–100).
