# Fix pipeline — deterministic test-suite reorganiser

The `axm-audit fix` subcommand and the `audit_fix` MCP tool
([`AuditFixTool`](../src/axm_audit/tools/audit_fix.py) in
`axm_audit.tools.audit_fix`) drive a deterministic pipeline that
batch-relocates, splits, merges and renames test files to satisfy the
AXM 3-level pyramid + canonical naming conventions. It consumes findings from three rules:

- `TEST_QUALITY_PYRAMID_LEVEL` (unit vs integration vs e2e)
- `TEST_QUALITY_FILE_NAMING` (`test_{symA}__{symB}.py` for integration/e2e)
- `TEST_QUALITY_NO_PACKAGE_SYMBOL` (out-of-pipeline; surfaced for manual
  review)

The pipeline runs in dry-run by default and mutates only on `--apply`.

## Pipeline architecture

```
0.5 NON-CANONICAL-RELOCATE  tests/functional/*  → tests/integration/
0.  FLATTEN                 heterogeneous Test* classes → top-level funcs
1.  RELOCATE                PYRAMID_LEVEL mismatch → git mv across tiers
1.5 FLATTEN_LAYOUT          tests/<tier>/<subdir>/ → flat layout
2.  SPLIT                   FILE_NAMING verdict=SPLIT     → anvil moves units
3.  COLLIDE / MERGE         FILE_NAMING verdict=COLLIDE   → anvil moves units
4.  RENAME                  FILE_NAMING verdict=NAME_MISMATCH → git mv
```

The whole pipeline runs inside a fixed-point loop (`MAX_ITERATIONS=6`),
since each mutation can expose new findings the audit could not see on
the previous iteration. Iteration stops early when a pass emits zero ops.
In dry-run mode the loop runs exactly once (no mutation).

`NO_PACKAGE_SYMBOL` findings are out-of-pipeline — the verdict is
context-dependent (legitimate formal check vs. candidate for deletion)
and surfaced in a separate report section pointing the user to
`/scenario-rename` or manual inspection.

## Module layout (hexagonal split)

The applicator lives at `src/axm_audit/core/fix/`, 12 modules organised by
hexagonal layer:

```
core/fix/
├── __init__.py             — public API: run, format_report, PipelineReport, FileOp
├── models.py               — FileOp, OpKind, PipelineReport + constants
│                             (NON_DETERMINISTIC_RULES, CANONICAL_TIERS, MAX_ITERATIONS, TOP_K)
├── io_primitives.py        — _cst_load/save/top_level/unwrap + _git_mv
├── paths.py                — _tier_for_path, _retier, _safe_filename,
│                             _module_path_for_test_file, _file_depth_from_project
├── tests_ast.py            — read-only AST: tests, classes (pathological detection),
│                             helpers, markers (usefixtures), imports analysis
├── cst_rewrite.py          — write CST: flatten class, rename, delete, reorder,
│                             depth patch (__file__), imports (insert/dedupe/
│                             backfill) + project import index cache
├── findings.py             — audit ingestion, canonical filename, collect_unfixable
├── layout_and_move.py      — relocate_non_canonical_tiers (Stage 0.5),
│                             flatten_tier_layout (Stage 1.5),
│                             _rewrite_cross_test_imports,
│                             _safe_move_units (wraps anvil),
│                             _resolve_helper_conflicts / _resolve_conftest_shadowing
├── stages_plan.py          — plan_flatten / plan_relocate / plan_naming (pure)
├── stages_execute.py       — _execute_flatten/_relocate/_rename/_split/_merge
│                             + execute() dispatcher
├── extract_helpers.py      — post-pipeline helper extraction to
│                             tests/<tier>/_helpers.py or conftest.py
├── pipeline.py             — run() + fixed-point loop + _ruff_format_tests
└── report.py               — format_report CLI output
```

### Dependency layers

```
report          → models
pipeline        → models, stages_plan, stages_execute, extract_helpers,
                  layout_and_move, cst_rewrite, findings
extract_helpers → cst_rewrite, io_primitives, paths, tests_ast
stages_execute  → cst_rewrite, findings, io_primitives, layout_and_move,
                  models, paths, tests_ast
stages_plan     → findings, models, paths, tests_ast
layout_and_move → cst_rewrite, io_primitives, models, paths, tests_ast
findings        → models, paths, tests_ast, (lazy: stages_plan)
cst_rewrite     → io_primitives, paths, tests_ast
tests_ast       → (stdlib only)
paths           → (stdlib only)
io_primitives   → libcst
models          → (stdlib only)
```

One lazy cycle: `findings.collect_unfixable → stages_plan.plan_flatten`
(needed to surface pathological FILE_NAMING cases the pipeline can't
auto-fix).

## Real-world surprises (documented in the code)

1. **Anvil's `rename=` param doesn't help cross-file collisions** — it
   validates target absence under the *original* name before applying
   the rename. The pipeline works around it by renaming the symbol in
   source first (via `_rename_top_level_in_source` in `cst_rewrite.py`),
   then handing anvil a clean conflict-free move.

2. **`audit_project()` cache breaks after in-flight mutations** —
   calling it post-apply raises `FileNotFoundError` on cached paths.
   `collect_unfixable()` in `findings.py` swallows the exception
   defensively.

3. **`if TYPE_CHECKING:` imports are invisible to anvil** —
   `MockerFixture` imported only inside that block is treated as
   not-imported when the symbol using it (only via type annotation) is
   moved. `_backfill_missing_imports()` in `cst_rewrite.py` walks
   `if TYPE_CHECKING:` blocks and reproduces the wrapper at the target.

## Bug-class history

The pipeline went through 14 iteration passes during productisation.
The four resolved bug classes worth remembering:

### B1 — pathological-AND-heterogeneous Test* classes

A class with divergent canonicals AND a feature blocking flatten
(`self.<attr>`, custom base, `__init__`) survives Stage 0 silently and
breaks Stage 2 SPLIT (which can only route 4 of 5 canonical targets).
`_file_has_pathological_class()` (`tests_ast.py`) is a cheap pre-check
used by `plan_naming` (`stages_plan.py`) to skip SPLIT planning for
affected files. Pathological cases now surface as `collect_unfixable`
entries pointing to `/scenario-rename`.

### B2 — SPLIT/MERGE/RENAME planned for non-canonical tier paths

Planner emitted ops for `tests/functional/test_X.py` but executor
skipped them silently. `plan_naming` (`stages_plan.py`) now filters
so SPLIT/COLLIDE/RENAME only land on canonical paths; non-canonical
files are routed through Stage 0.5 RELOCATE first.

### B3 — convergence (unanimity rule)

The fixed-point loop oscillated on files containing tests with mixed
tier verdicts (one `integration` + one `unit`). `plan_relocate` used
to skip `cur == lvl` findings and only count mismatches, so when the
file lived in `integration/` it saw "1 finding → unit", relocated,
then on the next pass saw "1 finding → integration", and oscillated
forever.

Resolution: `plan_relocate` (`stages_plan.py`) now counts every test's
target level (including `cur == lvl` ones). A file is relocated only
when *all* tests agree on a single target distinct from the current
tier. Mixed files are left for manual `/scenario-rename` or hand-splitting.
Conservative on purpose: sacrifices some auto-resolution for guaranteed
convergence.

### B4 — non-canonical tier directories ignored

Files under `tests/functional/` (or any non-canonical tier) were tier-less,
so SPLIT/MERGE/RENAME silently refused them. `relocate_non_canonical_tiers()`
in `layout_and_move.py` now runs as Stage 0.5 (before Stage 1 RELOCATE)
and moves every non-canonical tier file into `tests/integration/`.
Subsequent stages then see only canonical paths. `CANONICAL_TIERS` in
`models.py` documents the allow-list (`unit`, `integration`, `e2e`).

`tests/fixtures/` is surgically excluded via the private
`_NON_TEST_DIR_NAMES` set in `layout_and_move.py` — by AXM convention
that directory holds static test data (corpora, snapshots, baselines)
consumed by real tests, not test files. Other non-canonical tiers
(`tests/functional/`, `tests/hooks/`, ...) are still relocated.

### B5 — non-atomic apply could corrupt a real suite

`run(apply=True)` mutated `tests/` in place with no transaction: any
exception mid-cascade (e.g. an unguarded `KeyError` on a runtime
suite-derived key in the import backfill, surfacing as an opaque
`"test_basic"`) left the tree half-written, and a botched move/split
could emit a module that no longer parses. The skill's parity/idempotence
invariants were only checked on the corpus, never enforced on the live
tree.

`run(apply=True)` is now wrapped by `_run_apply_atomic()`:

1. **snapshot** — `_snapshot_tests()` copies the whole `tests/` tree into
   a temp dir outside the project (so a botched in-place mutation can
   never touch the backup);
2. **mutate** — the fixed-point loop + post-polish run as before;
3. **collect gate** — `_collect_only_gate()` does an in-process
   `compile()` sweep of every `test_*.py` (the cheap, deterministic
   equivalent of `pytest --collect-only` for the dominant failure class:
   a file that no longer parses — a real subprocess per apply made the
   suite time out);
4. **promote / rollback** — on success the snapshot is discarded; on
   **any** exception or a failed gate, `_restore_tests()` restores the
   tree byte-identical and a `FixApplyError` with an actionable message
   is raised (never the bare `"test_basic"` token; the original cause is
   chained via `__cause__`).

Import-backfill hardening (`cst_rewrite.py`): `_extend_recoverable()`
guards both donor lookups against `KeyError` (a miss degrades to
"unresolved", never crashes), and a name that genuinely resolves to no
donor is reported as a structured `unresolved import for <name>` warning
(stashed under the `_UNRESOLVED_KEY` sentinel by
`_resolve_recoverable_imports` and re-emitted by
`_backfill_missing_imports`) instead of being dropped silently.
`TYPE_CHECKING`-only donor imports (e.g. `MockerFixture` used solely in a
method-parameter annotation under `if TYPE_CHECKING:`) are carried into
every split/relocate target that references them, so collection no longer
fails with a post-fix `NameError`.

## Hardened edge cases (collateral fixes)

Bug classes uncovered during cross-corpus validation. Each entry
explains a non-obvious code path you'd otherwise wonder about:

- **`_make_pkg` signature drift across files** — `_resolve_helper_conflicts()`
  (`layout_and_move.py`) renames the source-side helper to
  `H__from_<stem>` when source and target define helpers with the same
  name but different bodies. `shared_helpers="duplicate"` then copies
  cleanly.
- **`@pytest.mark.usefixtures("X")` invisible to anvil** — anvil walks
  AST refs on moving symbols, but marker arguments are string literals,
  so fixtures injected via marker used to stay in source and disappear
  when source was stripped. `_collect_marker_fixtures_to_move()`
  (`tests_ast.py`) now scans moving units for `usefixtures` markers and
  adds the referenced fixtures to the move list when they're
  source-defined and not target-visible.
- **Decorator-referenced module-level constants dropped on SPLIT** — a
  test decorated with `@_alias` where `_alias = pytest.mark.skipif(...)`
  is a top-level Assign used to produce un-collectable target files:
  anvil moved the test but left `_alias` (and any constants it
  referenced like `CASES`) behind, then `_finalize_split_anchor`
  git-mv-renamed source to the anchor target with the moved constants
  already stripped from source — so even the anchor lost them.
  `_collect_module_level_deps_to_copy()` (`tests_ast.py`) computes the
  transitive closure of free-name references inside decorators of the
  moving units, restricted to top-level `Assign` / `AnnAssign` defs in
  source. `_copy_module_level_deps_to_target()` (`layout_and_move.py`)
  splices those statements into the target as text *after* anvil runs,
  without touching source — so the anchor's source-rename keeps the
  constants too. Closure follows chains (`B = A + 1` → also carry
  `A = 1`), preserves source order, and is surgical: unrelated
  top-level names are not carried.
- **SPLIT / MERGE module-level load-time order** — when a moving unit
  references names from its decorator chain (e.g.
  `def helper(): ...` + `CONST = helper()` +
  `_alias = pytest.mark.skipif(not CONST, ...)` +
  `@_alias @pytest.mark.parametrize("c", CONST)`), the combination of
  anvil's `shared_helpers="duplicate"` mode and
  `_copy_module_level_deps_to_target` can leave the target with
  top-level statements in an order that breaks module load
  (`_alias = ... not CONST ...` evaluating before `CONST = helper()`,
  or `CONST = helper()` evaluating before `def helper`).
  `_topological_reorder_decorator_deps()` (`layout_and_move.py`) runs
  as the last step of `_safe_move_units` and is **target-centric**:
  it builds a top-level dependency graph from the target tree alone,
  spanning `Assign` / `AnnAssign` / `FunctionDef` / `AsyncFunctionDef`
  / `ClassDef`. Free `Name(Load)` references are walked in
  `Assign.value` / `AnnAssign.value+annotation` and
  `FunctionDef.decorator_list` /
  `ClassDef.decorator_list+bases+keywords` — bodies of defs are NOT
  load-evaluated and are intentionally skipped. The **hoist set** is
  the transitive closure of names referenced by any module-level
  decorator; hoisted statements are topologically sorted (deps before
  dependents) and reinserted before the first remaining statement
  that load-time-references any hoisted name. The pre-anvil source
  tree is used **only** as a stable tiebreaker between valid
  linearisations — not as the source of truth for ordering, which
  matters when a target receives content from multiple `FileOp`s
  (split-with-multiple-targets, merge, or both): no single source
  tree describes all contributors. Statements outside the hoist set
  keep their existing relative position — the pass is surgical and
  idempotent (running it twice on a correctly-ordered target is a
  no-op).
- **`Path(__file__).parents[N]` drift after relocate** — a file moved
  from `tests/unit/core/test_X.py` (4-deep) to `tests/integration/test_X.py`
  (3-deep) keeps its `FIXTURES = Path(__file__).parents[2] / "fixtures"`
  constant, which now points to project root instead of `tests/`.
  `_patch_file_dunder_depth()` (`cst_rewrite.py`) detects the depth
  delta from `_file_depth_from_project()` and rewrites both surface
  forms (`parents[N]` subscript and `.parent.parent...` chains) via
  libcst. The id-collection pre-pass MUST run *after* `_DunderPatcher`
  since libcst rebuilds nodes during any visit (even no-op transforms),
  so original `module` ids are stale by the time `_PatchChainOnce` runs.
- **Conftest fixture shadowing on MERGE** — when source has no local
  fixture `X` (relies on conftest's body) but target has a local `X`
  with a different body, the moved tests bind to target's local at
  runtime and fail with `Symbol not found`. `_resolve_helper_conflicts`
  also renames the source-side helper when target lacks it BUT a
  conftest on target's ancestor chain provides a fixture of the same
  name. `_collect_conftest_fixtures()` (`tests_ast.py`) walks the chain.
- **Helper-rename misses transitive references** — `_resolve_helper_conflicts`
  used to check helper collisions only against names *directly*
  referenced by the moving units. A test consuming a fixture which
  itself calls a helper would miss the helper at rename time and bind
  to target's same-named but body-different version. Fix: extend
  `referenced` with a fixed-point closure that walks names → source
  helpers → names-they-reference until no new helpers appear.
- **Promoted helper's dependencies left behind** — when
  `_extract_shared_helpers_in_tier()` (`extract_helpers.py`) promotes a
  fixture to `tests/conftest.py`, its helper dependencies (already
  living in `tests/<tier>/_helpers.py`) are not imported by the
  destination conftest. `_synth_import_from_helpers()` in
  `cst_rewrite.py` is a last-resort backfill in
  `_backfill_missing_imports()` that scans every `tests/<tier>/_helpers.py`
  for a top-level def of the missing name and synthesises a
  `from tests.<tier>._helpers import <name>` statement.
- **`_git_mv` silent overwrite** — the `shutil.move` fallback used when
  `git mv` refused (target exists) used to destroy pre-existing files.
  `_git_mv()` in `io_primitives.py` now raises `FileExistsError` on
  pre-existing targets; `_execute_relocate` / `_execute_rename`
  (`stages_execute.py`) re-route through `_safe_move_units` (via the
  `_reroute_through_safe_move` helper). The pre-call existence check
  is `exists()` (not `is_file()`) so a pre-existing directory at the
  target doesn't slip through.
- **`_git_mv` race when two ops target the same destination in one
  iteration** — `shutil.Error("Destination path already exists")` is
  caught and translated to `FileExistsError`, then re-routed through
  `_safe_move_units` (same path as the silent-overwrite case above).
- **`_retier` ate the `.py` extension for tests at `tests/` root** —
  for `tests/test_X.py` (no tier subdir yet) the function used to do
  `parts[1] = target_lvl` and return a directory path, then
  `_safe_move_units` crashed with `IsADirectoryError` on
  `ast.parse(target.read_text())`. `paths.py:_retier` now branches on
  `len(parts) == 2`: inject the tier between `tests` and the file
  instead of substituting at index 1.
- **Overlong renamed identifiers (E501)** — `_bounded_rename` in
  `_safe_move_units` (`layout_and_move.py`) falls back to a 6-char sha1
  digest of the stem (`__from_<digest>`) when the verbose form would
  push the def line past 88 chars. Stem hashing keeps cross-source-file
  uniqueness; the verbose form is preferred when it fits.
- **Split docstring placement (E402)** — SPLIT seeds a new file with a
  module docstring before anvil prepends imports. `_reorder_module_statements`
  (`cst_rewrite.py`) used to treat any leading `ast.Expr/Constant/str`
  as part of the import head, leaving the docstring after the imports
  (E402 trigger on every subsequent import). It now detects the
  docstring as a separate statement (PEP 257: must be the very first
  body element to count as one) and unconditionally promotes it to
  position 0 in the rewritten body.

## Forward-looking — possible migration to `axm-ast`

The higher-level helpers in `tests_ast.py` (`_top_level_test_classes`,
`_top_level_helpers`, `_collect_imported_names`) could move to `axm-ast`
if/when that package exposes raw `ast.Module` access (it currently wraps
everything in Pydantic models). The fine-grained walkers
(`_class_is_pathological`, `_marker_fixtures_in_unit`, `_func_body_hash`)
are too pytest-specific to belong in a general library — keep them here.

## Convergence + parity invariants

A correct pipeline run must satisfy:

- **Idempotence** — a second dry-run after `--apply` plans zero ops.
- **Parity** — pass count and coverage % are unchanged across `--apply`.
  Drift in either direction is a red flag (a test was silently
  dropped/duplicated, or a fixture extraction broke isolation).
- **Monotonicity** — pyramid score never decreases across iterations.

These invariants are enforced by source-level tests under `tests/`. They
are not a runtime burden — the pipeline runs the same regardless.

## Out of pipeline (agent-driven follow-ups)

- `TEST_QUALITY_DUPLICATE_TESTS` → `/dedup-tests`
- `TEST_QUALITY_PRIVATE_IMPORTS` → `/private-imports-clear`
- `TEST_QUALITY_PYRAMID_LEVEL` (residual mixed-tier files) →
  `/pyramid-relocate`
- `TEST_QUALITY_TAUTOLOGY` → `/tautology-clear`
- `PRACTICE_TEST_MIRROR` → `/mirror-fix`
- `TEST_QUALITY_NO_PACKAGE_SYMBOL` → `/scenario-rename` or manual
  deletion review.
