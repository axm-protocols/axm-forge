# Python check catalogue

### pyproject (29 pts)

Configuration completeness of `pyproject.toml`:

| Check | Weight | What It Verifies |
|-------|--------|-----------------|
| `pyproject.pyproject_exists` | 4 | File exists and is valid TOML |
| `pyproject.pyproject_urls` | 3 | Homepage, Documentation, Repository, Issues |
| `pyproject.pyproject_dynamic_version` | 3 | `dynamic = ["version"]` + hatch-vcs |
| `pyproject.pyproject_mypy` | 3 | strict, pretty, disallow_incomplete_defs, check_untyped_defs |
| `pyproject.pyproject_ruff` | 3 | per-file-ignores + known-first-party |
| `pyproject.pyproject_pytest` | 4 | strict-markers, strict-config, import-mode, pythonpath, filterwarnings |
| `pyproject.pyproject_coverage` | 4 | branch, relative_files, xml output, exclude_lines |
| `pyproject.pyproject_classifiers` | 1 | Development Status, Python version, Typing :: Typed |
| `pyproject.pyproject_ruff_rules` | 2 | Essential rules: E, F, I, UP, B, S, BLE, PLR, N |
| `pyproject.pyproject_wheel_doc_shipping` | 2 | Shipping docs wired through wheel `force-include` |

### ci (16 pts)

GitHub Actions CI workflow:

| Check | Weight | What It Verifies |
|-------|--------|-----------------|
| `ci.ci_steps_executable` | 4 | At least one `.yml`/`.yaml` workflow exists and every step declares `uses` or `run` |
| `ci.ci_lint_job` | 3 | Lint/type-check job |
| `ci.ci_test_job` | 3 | Test job with Python matrix |
| `ci.ci_security_job` | 2 | pip-audit security scanning |
| `ci.trusted_publishing` | 2 | OIDC Trusted Publishing without API token fallback |
| `ci.dependabot` | 2 | `.github/dependabot.yml` configured |

The executable-step check scans every workflow under `.github/workflows/`. Fields
such as `name`, `with`, `env`, `if`, and `continue-on-error` may decorate a
step, but do not replace its required `uses` or `run` key. Jobs without a
`steps` block, including reusable workflows declared with job-level `uses`, are
ignored.

### tooling (16 pts)

Developer tooling configuration:

| Check | Weight | What It Verifies |
|-------|--------|-----------------|
| `tooling.precommit_exists` | 3 | `.pre-commit-config.yaml` exists |
| `tooling.precommit_ruff` | 2 | Ruff hook |
| `tooling.precommit_mypy` | 2 | MyPy hook |
| `tooling.precommit_conventional` | 2 | Conventional commits hook |
| `tooling.precommit_basic` | 1 | trailing-whitespace, end-of-file-fixer, check-yaml |
| `tooling.precommit_installed` | 2 | Pre-commit hooks activated in `.git/hooks/` |
| `tooling.makefile` | 4 | All standard targets (install, check, lint, format, test, audit, clean, docs-serve) |

### docs (18 pts)

Documentation setup:

| Check | Weight | What It Verifies |
|-------|--------|-----------------|
| `docs.mkdocs_exists` | 3 | `mkdocs.yml` exists |
| `docs.diataxis_nav` | 3 | Tutorials + How-To + Reference + Explanation |
| `docs.plugins` | 3 | gen-files, literate-nav, mkdocstrings |
| `docs.gen_ref_pages` | 2 | `docs/gen_ref_pages.py` for auto API docs |
| `docs.readme` | 3 | Features, Installation, Development, License sections |
| `docs.readme_badges` | 2 | axm-audit + axm-init badges in README |
| `docs.standalone_api_ref` | 2 | If local nav declares `reference/api/`, require local gen-files, literate-nav, mkdocstrings and `docs/gen_ref_pages.py`; otherwise pass |

### structure (17 pts)

Project structure:

| Check | Weight | What It Verifies |
|-------|--------|-----------------|
| `structure.src_layout` | 4 | `src/<pkg>/__init__.py` |
| `structure.py_typed` | 2 | PEP 561 `py.typed` marker |
| `structure.tests_dir` | 3 | `tests/` with `test_*.py` files |
| `structure.contributing` | 2 | `CONTRIBUTING.md` exists |
| `structure.license_file` | 3 | `LICENSE` file exists |
| `structure.uv_lock` | 2 | `uv.lock` committed for reproducible builds |
| `structure.python_version` | 1 | `.python-version` file for pinned Python |

### deps (5 pts)

Dependency groups:

| Check | Weight | What It Verifies |
|-------|--------|-----------------|
| `deps.dev_deps` | 3 | pytest, pytest-xdist, ruff, mypy, prek in dev group (legacy pre-commit passes with a migration hint) |
| `deps.docs_group` | 2 | mkdocs-material, mkdocstrings, gen-files, literate-nav |

!!! note "Members"
    `deps.docs_group` is skipped for workspace members — the docs dependencies
    live at the monorepo root, so a member only counts `deps.dev_deps` here.

### changelog (5 pts)

Changelog management:

| Check | Weight | What It Verifies |
|-------|--------|-----------------|
| `changelog.gitcliff_config` | 3 | `[tool.git-cliff]` in pyproject.toml |
| `changelog.no_manual_changelog` | 2 | No manual CHANGELOG.md (git-cliff auto-generates) |

### workspace (21 pts)

Workspace-specific checks — only run when the project context is `WORKSPACE`:

| Check | Weight | What It Verifies |
|-------|--------|------------------|
| `workspace.packages_layout` | 3 | Members live under `packages/` subdirectory |
| `workspace.members_consistent` | 2 | Each member has `pyproject.toml`, `src/`, and a `tests_*` directory (canonical name: `tests_<normalized-package>/`) |
| `workspace.monorepo_plugin` | 2 | Root `mkdocs.yml` uses the `monorepo` plugin |
| `workspace.matrix_packages` | 2 | CI uses `--package` for per-member testing |
| `workspace.requires_python_compat` | 1 | Coherent `requires-python` across members |
| `workspace.root_name_collision` | 3 | Root project name does not collide with member names |
| `workspace.pytest_importmode` | 2 | Root pytest config has `import_mode = "importlib"` |
| `workspace.pytest_testpaths` | 2 | Root testpaths references member test directories |
| `workspace.quality_workflow` | 2 | `.github/workflows/axm-quality.yml` with per-package audit |
| `workspace.suite_dir_uniqueness` | 2 | Members have distinct test-suite directory names |

!!! note "Context-aware"
    Workspace checks are automatically skipped for standalone projects, workspace members, papers and experiments.
    The check engine detects the project context (standalone, member, workspace, paper, experiment) from
    `[tool.uv.workspace]` and the paper markers.

### paper (15 pts)

A paper — an `[tool.axm-lab]` project, or a satellite paper recognised by its
`paper/` + `experiments/` + `PLAN*.md` triple — carries none of a package's
invariants, so it is scored on its own:

| Check | Weight | What It Verifies |
|-------|--------|------------------|
| `paper.paper_structure` | 5 | `paper/`, `experiments/`, `README.md` and `PIPELINE.md` all present; `INDEX.md` is also required once an immediate experiment subdirectory has a `manifest.yaml` (a failure names every missing entry, in its message and in its fix) |
| `paper.plan_present` | 5 | `PLAN.md` at the paper root opens with a `---` delimited, non-empty YAML front-matter block |
| `paper.research_present` | 5 | `RESEARCH.md` at the paper root opens with a `---` delimited, non-empty YAML front-matter block — presence and form only, the header's keys are never read |

!!! note "A paper skips the packaging rulebook"
    The three `paper.*` checks run **only** when the detected context is `PAPER`; they are
    skipped for standalone projects, workspace roots and members. Conversely a paper skips
    every packaging check — `SKIP_BY_CONTEXT[PAPER]` is derived as *everything that is not a*
    `paper.*` *check* — so its report carries no Trusted Publishing, CI-matrix, mkdocs,
    dependabot, lock-file, classifiers, coverage or ruff/mypy finding, and its score stays
    meaningful.

### experiment (10 pts)

An experiment folder — a directory whose root `manifest.yaml` declares both
`contract_version` and `id` — is graded on the **form** its scaffold must carry:

| Check | Weight | What It Verifies |
|-------|--------|------------------|
| `experiment.experiment_structure` | 5 | `inputs/`, `scripts/`, `outputs/`, `analysis/` and `figures/` all present (a failure names exactly the missing directories) |
| `experiment.experiment_files` | 5 | `manifest.yaml` and `README.md` at the experiment root — existence only (a failure names exactly the missing file(s)) |

!!! note "Form here, substance elsewhere"
    Neither check reads the **content** of `manifest.yaml`: a freshly scaffolded
    experiment whose manifest still holds `TODO` placeholders passes both. Manifest
    validity, input hashing, DAG coherence, freeze anteriority and metrics are the job
    of axm-lab's `experiment_check` — axm-init never duplicates them. Symmetrically the
    two `experiment.*` ids are skipped for standalone projects, workspace roots, members
    and papers, so a Python package is never reproached an experiment check.


### protocols (6 pts, explicit-only)

Protocol-profile checks run only when the `protocols` category is requested:

| Check | Weight | What It Verifies |
|-------|--------|------------------|
| `protocols.profile` | 4 | Profile metadata, distribution/module identity, required layout, and bidirectional component inventory |
| `protocols.protocols_resources` | 2 | Every declared prompt has a `prompts/<name>.md` resource and the protocol package is explicitly included in the wheel |

Prompt existence and distribution inclusion are independent invariants. A local
file is not sufficient evidence that Hatch will ship it. For a domain such as
`dev`, declare the package mapping explicitly:

```toml
[tool.hatch.build.targets.wheel.force-include]
"src/protocols_dev" = "protocols_dev"
```

A missing prompt finding names its expected repository-relative path and the
correction. A missing distribution mapping names `pyproject.toml`, every affected
prompt path, and the required `force-include` declaration. At a workspace root,
findings retain the member identity. Projects without a protocol profile remain
not applicable.

## Framework-specific registries

The tables above describe Python. Without `package.json`, detection selects
Python. With `package.json`, Svelte configuration or a Svelte dependency takes
precedence, then a React dependency, then Node.

Node and React use the Node registry: `package_json`, `tsconfig`, `tooling`,
`structure`, `ci`, `docs`, `changelog`, `workspace`. Svelte adds `config`.
Framework selection and project-context detection are independent:
context still follows the paper/experiment and uv-workspace markers.
`init_check` has no CLI `--framework` override.

Counts depend on registry revision, context and configured exclusions. The
current Python catalogue has 57 declared functions, of which
`ci.ci_workflow_exists` is superseded by `ci.ci_steps_executable` and skipped.
This yields 56 active catalogue entries, not 56 checks on every project.
Use the actual report as the authority for a run's coverage.

See [grade calculation](../../explanation/check-grades.md) and
[project contexts](../../explanation/project-contexts.md).

## Paper check implementation boundary

Paper invariants, run only in the `PAPER` context: `check_paper_structure` (`paper/`, `experiments/`, `README.md`, `PIPELINE.md` — the provenance document of the shared data cohort, rendered at the paper root by the `paper-submodule` template in both flavours — plus `INDEX.md` once experiments have manifests), `check_plan_present` (`PLAN.md` opening with a `---` YAML front-matter block) and `check_research_present` (`RESEARCH.md`, the research protocol document, same rule).

The last two share the private `_front_matter_document(project, filename, check_name, intention)` helper, itself built on the pure `_parse_front_matter` parser, so presence + non-empty front-matter is graded identically for every paper document.

FORM only: the header's keys (`gap`, `investigations`, a status) are never read — that substance belongs to the package owning the authoritative model, and axm-init carries no dependency toward it

## Experiment check implementation boundary

Experiment FORM invariants, run only in the `EXPERIMENT` context: `check_experiment_structure` (`inputs/`, `scripts/`, `outputs/`, `analysis/`, `figures/` all present) and `check_experiment_files` (`manifest.yaml` + `README.md` at the root, existence only).

Both name EXACTLY the missing entries, computed by the pure filesystem-free `_missing_entries(required, present)` helper, and NEITHER opens the manifest — a freshly scaffolded experiment whose manifest still holds TODO placeholders passes.

Substance (contract validity, input hashing, DAG coherence, freeze anteriority, metrics) belongs to axm-lab's `experiment_check` and is deliberately never duplicated here, so axm-init carries no dependency toward axm-lab
