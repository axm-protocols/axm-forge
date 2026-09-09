# Build and maintain the workspace documentation

Run from the repository root after
`uv sync --all-packages --all-groups`.

## Build and preview

```bash
uv run mkdocs build --strict
uv run mkdocs serve --dev-addr 127.0.0.1:8000
```

The build writes `site/` by default. The preview serves the site at
[http://127.0.0.1:8000](http://127.0.0.1:8000); stop it with Ctrl-C.
Choose another port if that one is occupied. These commands do not deploy.

For an output outside the checkout:

```bash
uv run mkdocs build --strict --site-dir /tmp/axm-forge-site
```

## Put content in its owning layer

| Content | Source |
|---|---|
| Repository overview | `README.md` |
| Published homepage | `docs/index.md` |
| Package selection | `docs/packages/index.md` |
| Shared contribution guide | `CONTRIBUTING.md`, included by `docs/contributing.md` |
| Cross-package explanations and workflows | Root `docs/explanation/`, `docs/howto/`, `docs/tutorials/` |
| A package's contract or tutorial | `packages/<package>/docs/` |
| Current Node/Svelte support overview | `docs/node-svelte/index.md` |

The README is not automatically the site homepage. Maintain both entry points
without duplicating the complete package references.

## Navigation and API generation

Root `mkdocs.yml` uses the monorepo plugin to include each member's
`mkdocs.yml`. Package sections use their configured site names as URL
prefixes (for example `edit/` or `axm-config/`).

The root `docs/gen_ref_pages.py` scans package `src/` trees and emits
module references below `reference/`. It excludes templates, resources,
`__main__` and generated `_version` modules. Package API landing pages
provide reader-facing entry points into their public contracts.

When adding a page, add it to the owning navigation. When adding a package,
also update its root include, mkdocstrings source path and the catalog.
Use source-relative Markdown links within the assembled docs tree; verify
their rendered destinations after building.

## Validate the result

1. Run the strict root build, not only the changed package's standalone build.
2. Check that new pages are in navigation and appear in the expected section.
3. Follow links and anchors, including cross-package links and generated API.
4. Check examples against current CLI help and Python signatures; execute
   meaningful scenarios in temporary fixtures.
5. Remove obsolete proposals from the published site; Git history retains them.

Strict mode raises reported warnings, but does not validate every remote URL
or execute code examples. Generated API coverage also does not establish
the correctness of prose.

## Publication

The checked-in `Publish Docs` workflow builds on selected documentation
changes to main or manual dispatch, then deploys through Cloudflare.
Its build command currently omits `--strict`; use the stricter local
command before submitting changes.

The workflow's path filter covers `docs/**`, package docs/configs,
root `mkdocs.yml` and `wrangler.toml`. A change only to the root
README or CONTRIBUTING file does not trigger it, even though CONTRIBUTING
is included at build time. Include the corresponding documentation change
when appropriate or use the documented manual workflow trigger.
