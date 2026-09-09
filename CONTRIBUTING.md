# Contributing to axm-forge

Forge is a uv workspace. Run the commands below from its root unless a
package directory is specified. Python 3.12+, uv and Git are required;
package tests may also need local external tools.

## Development setup

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-packages --all-groups
uv run prek install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push
```

The sync installs all members and development/documentation groups into the
workspace environment. Package extras are separate. For example, analysis of
TypeScript requires axm-ast's `typescript` extra; Node quality checks also
need the target project's configured Node tools.

## Making changes

1. Create a branch and scope the change to the relevant package or workspace files.
2. Read that package's public contracts and tests.
3. Run the package tests and the applicable lint/type checks.
4. Build documentation when examples, APIs, navigation or prose change.
5. Commit with a conventional message such as `docs(axm-edit): clarify rollback`.
6. Open a pull request with behavior changes, validation and remaining limits.

Avoid unrelated formatting or generated-file changes. Each package's
`pyproject.toml` owns its test and typing configuration.

## Tests and checks

Run one package with its own configuration:

```bash
uv run --package axm-edit --directory packages/axm-edit pytest --cov
```

Replace `axm-edit` in both positions. To exercise every current member
without a manually maintained package list:

```bash
for package_dir in packages/*; do
  [ -f "$package_dir/pyproject.toml" ] || continue
  package_name="${package_dir##*/}"
  uv run --package "$package_name" --directory "$package_dir" pytest --cov || exit 1
done
```

Workspace-level tests live in `tests/` and are separate from the member
suites:

```bash
uv run pytest tests --no-cov
make lint
```

`make lint` runs Ruff lint/format checks and per-package mypy. The
pre-push hook calls it; it does not run the full test matrix. Existing
pre-commit mypy hooks are scoped to the packages declared in
`.pre-commit-config.yaml`.

### Current Makefile scope

| Command | Actual scope |
|---|---|
| `make install` | All packages and dependency groups |
| `make test-all`, `make test` | Anvil, AST, audit, edit, init, git and smelt only |
| `make test-edit` (also anvil/ast/audit/init/git/smelt) | One of those seven packages |
| `make lint` | Global Ruff and mypy over all 14 listed packages |
| `make check` | Lint plus the seven-package test loop |
| `make axm-audit`, `make axm-init`, `make quality` | Audit/governance commands over the same seven packages |
| `make docs-build`, `make docs-serve` | Root MkDocs build (strict) or preview |

The `test-axm-ingot` and `test-axm-echo` targets currently pass
`--package` to pytest instead of uv. Use the explicit per-package command
above for those packages. Do not use `make quality`'s process exit code as
a substitute for reading audit/governance findings.

CI discovers members from `[tool.uv.workspace]`, including its exclusions,
through the shared `workspace-matrix` action. It reads each package's actual
project name and test paths, then tests changed packages and their transitive
dependants on Python 3.12/3.13. Shared infrastructure changes or an unavailable
Git comparison trigger the full matrix. Ruff runs globally; mypy uses the same
affected member set. Security auditing remains advisory.

The quality workflow recomputes reports and badges for every current member
on each push to main, then aggregates only that run's reports. Missing coverage
contributes zero. Removed members do not survive in the published snapshot.
Newer runs cancel older ones, and publication checks that the checkout still
matches main. A green workflow does not mean every reported quality rule passed.

## Documentation

The README is the repository entry point. The published homepage is
`docs/index.md`; each package has its own `docs/` and `mkdocs.yml`.
Workspace prose should explain package selection and shared workflows, with
links to package-owned contracts.

```bash
uv run mkdocs build --strict
uv run mkdocs serve --dev-addr 127.0.0.1:8000
```

Review navigation, local links and rendered API pages as well as build success.
Generated API pages come from `docs/gen_ref_pages.py`; do not edit files
under `site/`. See the
[documentation maintenance guide](https://forge.axm-protocols.io/howto/documentation/)
for the build layout and shared-page conventions.

## Adding a package

The uv membership glob is `packages/*`, but membership alone does not wire
every repository integration. Use axm-init's workspace-member scaffolding
guide, then review:

- Root workspace sources and the lockfile.
- Package metadata, source layout and `tests_<module_name>/` configuration.
- Root test paths, Makefile lists and hooks.
- The generated CI discovery output (no package list to update).
- Root MkDocs include, Python handler path, README and package catalog.

The documentation catalog remains explicit; CI membership is automatic. Follow the
[axm-init template reference](https://forge.axm-protocols.io/init/reference/templates/)
for the supported scaffold routes.

## Releases

Packages are independently versioned using tags such as
`axm-ast/v0.5.2`. The full package prefix selects its directory in the
publish workflow. Review that workflow and package metadata before tagging;
tag pushes can upload artifacts. Updating docs on main does not create a
package release.
