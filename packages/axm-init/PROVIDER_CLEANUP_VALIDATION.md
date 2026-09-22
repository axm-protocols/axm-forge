# Required domain providers — breaking cleanup

This supersedes the fallback/legacy routing boundaries in
`PROVIDER_VALIDATION.md`; that report remains as historical evidence.

## Delivered contract

- Forge retains the shared renderer/rule runner and Python, Node/Svelte,
  workspace/member primitives. Learning templates, rules and metadata are
  provided by installed `axm-learning[scaffold]`; missing providers or required
  hooks produce installation/version guidance, never bundled fallback.
- Removed Forge's experiment and Learning template trees, experiment rules,
  Learning business implementations, and `legacy_experiment_layers` routing.
  `init_scaffold(kind="experiment")` and experiment checks direct callers to
  Lab's ownership-aware `experiment_scaffold` / `experiment_check` tools.
- Paper remains a writing scaffold. It no longer emits flat `experiments/`,
  `RESEARCH.md`, or `[tool.axm-lab]`, nor requires a generated legacy index.
  PLAN plus paper source identifies both writing variants; existing explicit
  markers remain recognized. Documentation directs research selection to
  downstream `research.yaml`, without fabricating that selection.
- Learning removes its unused separate `learning-profile` template and
  `profile_template` accessor. Its active provider still supports roots,
  members, existing-project overlays, metadata and configuration checks.

All removed content is recoverable from the preceding Git revisions. No user
research, original checkout, remote branch, merge, or release was modified.

## Observed red → green

Commands use Forge's isolated `.venv/bin/python` unless stated otherwise.

1. `-m pytest packages/axm-init/tests_axm_init/integration/test_required_domain_providers.py -q --no-cov`
   initially failed **6 tests**: absent-provider rendering, local metadata
   fallback, legacy experiment routing, and bundled assets. The initial paper
   provider requirement was withdrawn after coordinator scope clarification.
   The experiment expectation was changed to the coordinator-approved
   ownership-aware Lab redirect and observed failing before that change.
2. The same file separately demonstrated red for bundled experiment rules,
   flat paper experiments, paper Lab metadata, missing investigation install
   guidance, and the zero-check experiment success. Final result: **9 passed**.
3. Learning's `test_assets.py::test_obsolete_profile_template_is_removed`
   failed before deletion, then passed. Existing overlay/rerun tests now use
   `layers(ScaffoldRequest(..., existing=True))` instead of the removed accessor.

Tests for deliberately removed 1.x manifest rendering, legacy experiment form
rules and RESEARCH.md authority were deleted or rewritten as refusal/absence
contracts. Learning rule tests remain in Learning; Forge tests its delegation.
Existing-project rerun tests now assert preservation of authored base tooling.

## Regression and static verification

```sh
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m pytest packages/axm-init/tests_axm_init -q -o addopts=''
```

**1141 passed, 1 skipped**, including slow and end-to-end tests. Subsequent
paper-metadata removal and context-table cleanup passed all **36** tests in
`test_required_domain_providers.py`, `test_copier_adapter__template_type.py`,
and `unit/core/test_checker.py`. Template matrix regression: **38 passed**.

Full axm-init source/tests Ruff lint and format passed; mypy with
`--follow-imports=silent --exclude '/templates/'` passed **57 source files**.
Template directories are Jinja source, not importable Python packages.
Installed the already-lockfile-pinned `types-pyyaml==6.0.12.20260906` into the
isolated environment for full typing; no dependency manifests/lockfiles changed.

## Actual installed cross-provider integration

Installed editable providers with `uv pip install --python .venv/bin/python
--no-deps -e ...` from the assigned Learning and Knowledge worktrees.

```sh
.venv/bin/python -m pytest /home/gjarry/orca/workspaces/axm-learning/feat-domain-scaffolds/packages/axm-learning/tests_axm_learning --import-mode=importlib -q -o addopts=''
.venv/bin/python -m pytest /home/gjarry/orca/workspaces/axm-knowledge/feat-investigation-scaffolds/packages/axm-lab/tests/integration/test_research_scaffold.py --import-mode=importlib -q -o addopts=''
```

Results: **183 Learning tests passed; 5 modern Lab integration tests passed**.
Lab tests use real installed entry points, create modern investigations and
owned 2.0 experiments, check no-overwrite and activation refusal, and confirm
the legacy hook is absent. Learning exercises real Copier rendering, root and
member metadata, authored-file preservation, and full provider discovery.
Learning source/tests lint/format passed; mypy passed **33 source files**.

## Wheel evidence and limitations

Built both wheels with `uv build packages/<package> --wheel --out-dir
.venv/validation-wheels` in their respective worktrees. ZIP inspection confirms
axm-init contains no experiment/Learning business templates, experiment rule
module, or RESEARCH.md template, while all six primitive/writing template
configs remain. Learning's wheel contains its current `learning-project`
config and no obsolete `learning-profile` assets. Builds stay under the owned
worktrees; generated wheels are intentionally untracked.

The full suite has one environment-dependent docs-toolchain skip. No known
functional failures remain. Shared rendering still trusts provider templates,
is not transactional, and uses process-local locks, as before. Domain tests
require the installed provider packages; Forge does not add runtime imports or
hard runtime dependencies on them.
