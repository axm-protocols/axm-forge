# CI Badge

Add an `axm-init` check-score badge to your project.

## You probably already have it

If you created your package with `axm-init scaffold`, you're done — scaffolding
already emits a correct `.github/workflows/axm-quality.yml` that runs the
`axm-init` checks, generates the badge JSON (with the AXM logo inlined the right
way), and pushes it to the `gh-pages/badges/` branch. Most users need nothing
further; just add the README snippet below.

The rest of this page is for **retrofitting an existing repo** that wasn't
scaffolded.

## Retrofit an existing repo

### 1. Create the workflow

Add `.github/workflows/axm-quality.yml`:

```yaml
name: axm-init quality

on:
  push:
    branches: [main]

permissions:
  contents: write

jobs:
  init:
    name: AXM Init & Badge
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0
      - uses: astral-sh/setup-uv@v7
      - run: uv python install 3.12

# Verify action versions are current before using:
# - actions/checkout: https://github.com/actions/checkout/releases
# - astral-sh/setup-uv: https://github.com/astral-sh/setup-uv/releases
# - peaceiris/actions-gh-pages: https://github.com/peaceiris/actions-gh-pages/releases

      - name: Run AXM Init check
        id: init
        run: |
          RESULT=$(uvx axm-init check . --json) || true
          SCORE=$(echo "$RESULT" | jq '.score')
          GRADE=$(echo "$RESULT" | jq -r '.grade')
          echo "score=$SCORE" >> "$GITHUB_OUTPUT"
          echo "grade=$GRADE" >> "$GITHUB_OUTPUT"
          echo "📋 AXM Init: Score $SCORE/100 — Grade $GRADE"

      - name: Choose badge color
        id: color
        run: |
          SCORE=$(echo "${{ steps.init.outputs.score }}" | cut -d. -f1)
          if [ "$SCORE" -ge 95 ]; then COLOR="brightgreen"
          elif [ "$SCORE" -ge 80 ]; then COLOR="green"
          elif [ "$SCORE" -ge 60 ]; then COLOR="yellow"
          else COLOR="red"; fi
          echo "color=$COLOR" >> "$GITHUB_OUTPUT"

      - name: Generate badge JSON
        run: |
          mkdir -p badges
          LOGO_FILE=$(mktemp)
          curl -fsSL https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.svg \
            -o "$LOGO_FILE" || true

          if [ -s "$LOGO_FILE" ]; then
            jq -n \
              --arg score "${{ steps.init.outputs.score }}" \
              --arg color "${{ steps.color.outputs.color }}" \
              --rawfile logo "$LOGO_FILE" \
              '{
                schemaVersion: 1,
                label: "axm-init",
                message: "\($score)%",
                color: $color,
                style: "flat",
                logoSvg: $logo
              }' > badges/axm-init.json
          else
            jq -n \
              --arg score "${{ steps.init.outputs.score }}" \
              --arg color "${{ steps.color.outputs.color }}" \
              '{
                schemaVersion: 1,
                label: "axm-init",
                message: "\($score)%",
                color: $color,
                style: "flat"
              }' > badges/axm-init.json
          fi

      - name: Push badge to gh-pages
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_branch: gh-pages
          publish_dir: ./badges
          destination_dir: badges
          keep_files: true
          commit_message: "badge: update axm-init score"
```

!!! note "uvx vs uv run"
    Use `uvx axm-init` for external projects (installs from PyPI).
    Within the axm-init repo itself, we use `uv run axm-init` (local lib).

### Why the logo handling looks fiddly

shields.io renders the AXM logo from an inlined SVG in the `logoSvg` JSON field.
The SVG is fetched from the canonical forge URL:

```
https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.svg
```

If the `curl` 404s or fails, it writes an **empty** file, and an empty
`logoSvg: ""` makes shields.io reject the **whole** badge with "invalid
properties" — it silently fails to render. Hence the two guards above: fetch with
`|| true` so a transient network failure doesn't fail the job, and only inline the
logo when the file is **non-empty** (`[ -s ]`, *not* `[ -f ]` — the latter passes
for an empty file). When empty, the badge JSON is emitted without the `logoSvg`
key (graceful degradation to a logo-less badge).

### 2. Add the badge to your README

By AXM convention the badge **links to the canonical docs page**, not to the
Actions tab:

```markdown
[![axm-init](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/YOUR_ORG/YOUR_REPO/gh-pages/badges/axm-init.json)](https://forge.axm-protocols.io/init/)
```

The badge JSON lives at `gh-pages/badges/axm-init.json` for a standalone package.
In a uv-workspace **monorepo**, per-member badges live under
`badges/<member-name>/axm-init.json` (extra subdir), plus a workspace aggregate at
`badges/axm-init.json` — point each member's README at its own subdir path.

### 3. Push to main

The badge will appear after the first workflow run pushes to `gh-pages`.

!!! note "Stale badge?"
    After the first publish (or a fix), the badge can keep showing "package not
    found" or a stale score because shields.io caches the JSON and GitHub's camo
    image proxy re-caches on top. This is **not** a bug — it self-heals within
    ~1h. To check the real current state, hit the raw JSON or the shields
    endpoint with a cache-buster query param (e.g. append `?v=2`) rather than
    trusting the rendered image.

## Color Thresholds

| Score | Color |
|---|---|
| ≥ 95 | 🟢 `brightgreen` |
| ≥ 80 | 🟢 `green` |
| ≥ 60 | 🟡 `yellow` |
| < 60 | 🔴 `red` |
