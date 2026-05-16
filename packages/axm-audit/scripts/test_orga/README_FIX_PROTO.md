# `fix_proto/` — session note (2026-05-16, post-pass-14)

Companion to `tuple_naming_proto.py` (integration tuple detector, May 2026)
and `tuple_naming_e2e_proto.py` (e2e CLI tuple detector). This proto is
the **deterministic applicator** that consumes findings from the two
versioned rules (AXM-1721 `TEST_QUALITY_NO_PACKAGE_SYMBOL`, AXM-1722
`TEST_QUALITY_FILE_NAMING`) plus the existing `TEST_QUALITY_PYRAMID_LEVEL`,
and applies a 5-stage pipeline that physically moves / splits / merges /
renames test files using `axm-anvil.move_symbols` for CST-correct edits.

The intent is to produce an `axm-audit --fix` binary (ticket AXM-1723,
not yet created — see "Productisation plan" below) that runs in dry-run
by default and mutates only on `--apply`.

## Code layout (post-split, 2026-05-16)

Previously a 3835-LOC monolith (`tuple_fix_proto.py`). Now a 70-LOC CLI
shim + 12 modules organised by hexagonal layer:

```
scripts/test_orga/
├── tuple_fix_proto.py            70 LOC  — argparse CLI shim → fix_proto.run
└── fix_proto/
    ├── __init__.py               12     — public API: run, format_report, PipelineReport, FileOp
    ├── models.py                 64     — FileOp, OpKind, PipelineReport + constants
    │                                       (NON_DETERMINISTIC_RULES, CANONICAL_TIERS, MAX_ITERATIONS, TOP_K)
    ├── io_primitives.py          79     — _cst_load/save/top_level/unwrap + _git_mv
    ├── paths.py                  93     — _tier_for_path, _retier, _safe_filename,
    │                                       _module_path_for_test_file, _file_depth_from_project
    ├── tests_ast.py             558     — read-only AST: tests, classes (pathological detection),
    │                                       helpers, markers (usefixtures), imports analysis
    ├── cst_rewrite.py          1081     — write CST: flatten class, rename, delete, reorder,
    │                                       depth patch (__file__), imports (insert/dedupe/
    │                                       backfill) + project import index cache
    ├── findings.py              228     — audit ingestion, canonical filename, collect_unfixable
    ├── layout_and_move.py       590     — relocate_non_canonical_tiers (Stage 0.5),
    │                                       flatten_tier_layout (Stage 1.5),
    │                                       _rewrite_cross_test_imports,
    │                                       _safe_move_units (wraps anvil),
    │                                       _resolve_helper_conflicts / _resolve_conftest_shadowing
    ├── stages_plan.py           231     — plan_flatten / plan_relocate / plan_naming (pure)
    ├── stages_execute.py        312     — _execute_flatten/_relocate/_rename/_split/_merge
    │                                       + execute() dispatcher
    ├── extract_helpers.py       414     — post-pipeline helper extraction to
    │                                       tests/<tier>/_helpers.py or conftest.py
    ├── pipeline.py              214     — run() + fixed-point loop + _ruff_format_tests
    └── report.py                 73     — format_report CLI output
```

**Total**: 3949 LOC (+3 % vs the 3835-LOC monolith — overhead is
per-module imports and docstrings).

### Dependency layers (hexagonal)

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

One lazy cycle resolved: `findings.collect_unfixable → stages_plan.plan_flatten`
(needed to surface pathological FILE_NAMING cases the proto can't auto-fix).

### Opportunities to migrate to `axm-ast`

Documented in `tests_ast.py`'s module docstring: the higher-level
helpers (`_top_level_test_classes`, `_top_level_helpers`,
`_collect_imported_names`) could move to `axm-ast` if/when that
package exposes raw `ast.Module` access (it currently wraps everything
in Pydantic models). The fine-grained walkers
(`_class_is_pathological`, `_marker_fixtures_in_unit`,
`_func_body_hash`) are too specific to pytest semantics to belong in
a general lib.

## Pipeline architecture

```
0.5 NON-CANONICAL-RELOCATE  tests/functional/*  → tests/integration/  [B4 fix]
0.  FLATTEN                 heterogeneous Test* classes → top-level funcs
1.  RELOCATE                PYRAMID_LEVEL mismatch → git mv across tiers
1.5 FLATTEN_LAYOUT          tests/<tier>/<subdir>/ → flat layout
2.  SPLIT                   FILE_NAMING verdict=SPLIT     → anvil moves units
3.  COLLIDE / MERGE         FILE_NAMING verdict=COLLIDE   → anvil moves units
4.  RENAME                  FILE_NAMING verdict=NAME_MISMATCH → git mv
```

The whole pipeline runs inside a **fixed-point loop** (`MAX_ITERATIONS=6`,
B3 fix) since each mutation can expose new findings the audit could
not see on the previous iteration. Iteration stops early when a pass
emits zero ops.

`NO_PACKAGE_SYMBOL` findings are **out of pipeline** — the verdict is
context-dependent (legitimate formal check vs. candidate for deletion),
not auto-fixable. They appear in a separate report section pointing
the user to `/scenario-rename` or manual inspection.

The `NON_DETERMINISTIC_RULES` frozenset in `models.py` documents this
boundary in code, with the rationale in a comment.

## Test corpus

The proto was validated against copies of four packages at:

* `/tmp/proto-fix-init/` — `axm-init` (smallest, fastest feedback)
* `/tmp/proto-fix-git/`  — `axm-git`
* `/tmp/proto-fix-smelt/` — `axm-smelt`
* `/tmp/proto-fix-ast/`  — `axm-ast` (largest, ~1600 tests)

Each copy is preserved between runs via:

```bash
git -C /tmp/proto-fix-<corpus> reset --hard HEAD -q && \
git -C /tmp/proto-fix-<corpus> clean -qfdx
```

To recreate after a reboot:

```bash
PKG=axm-init  # or axm-git / axm-smelt / axm-ast
cp -R /Users/gabriel/Documents/Code/python/axm-workspaces/axm-forge/packages/$PKG /tmp/proto-fix-${PKG#axm-}
cd /tmp/proto-fix-${PKG#axm-} && rm -rf .git && git init -q && git add -A
git commit -q -m "baseline"
```

## History — 12 iteration passes

Each pass = one full `--apply` of the proto on the corpus, followed by
inspection of the result. The git commits are in
`packages/axm-audit/` of the main repo, not the `/tmp` copies.

| Pass | Commit | Key change | Verdict |
|------|--------|-----------|---------|
| 1  | `c2e185f` | Initial proto, dry-run only, detector inlined | Plan looks coherent |
| 2  | `0b921ac` | First full apply, collisions handled by suffix `__from_<stem>` | 122 ops applied, idempotent, but 197 integration tests vanished |
| 3  | `4d4c6b6` | Inter-stage **re-plan**: stages 2-4 see post-mutation paths via re-call to `plan_naming()` | Test count restored (1050 → 1050 via AST); idempotent |
| 4  | (uncommitted) | `_safe_filename()` `-` → `__` for PEP8; `_reorder_module_statements()` topological sort; `_backfill_missing_imports()` recovers lost imports (with TYPE_CHECKING preservation and cross-file fallback via `_scan_tests_for_import()`) | Pytest collection succeeds with 1401 tests, 0 ERROR; F821 = 0; N999 = 0 |
| 10 | `4528dee` | **Full libcst migration for mutating helpers** (preserves triple-quoted strings, comments, blank lines). ast remains for read-only analysis. Global import-index cache replaces per-name re-walk. Local-binding shadow detection in dedup. | Ruff 1 → 1 (zero regression; sole survivor is synthetic `S607` from baseline) |
| 11 | `293afb9` | **Silent-test-loss + body-mismatch hardening** (6 bug classes — see "Pass 11" below). Validated against axm-init, axm-git, axm-smelt, axm-ast. | 4 corpora: 0 failed / 0 errors / ruff clean |
| 12 | (this work, pre-split) | **4 fixes B1/B2/B3/B4** for proto convergence — see "Pass 12" section below. Pipeline output: 6 iterations, same op counts as pass 11. Pytest regressed 0 → 2 fails on axm-init. | B3 fixed-point does NOT converge — known open bug |
| split | (this work, post-split) | **Monolith → 12 modules** (hexagonal split). 70-LOC CLI shim. Iso-comportement validated: identical pipeline output (iterations, op counts), identical pytest result (2 failed / 662 passed), ruff clean. | Refactor only; no logic change |
| 13 | (this work) | **B3 convergence fix** (unanimity rule in `plan_relocate`) + 2 collateral bugs found while validating: `_retier` for files at `tests/` root (no tier component) + `_git_mv` race when target appears between check and move. See "Pass 13" section below. | B3 resolved on 5 corpora (init/git/smelt/ast/audit); convergence in 1-3 iterations; 0 oscillation |
| 14 | (this work) | **4 collateral bug fixes** found by extending validation to axm-audit: dunder double-patch (`_PatchChainOnce` visited bottom-up patched each chain link), helper-rename caller leak (transitive helper closure missing), E402 post-split (docstring not promoted to position 0), E501 long canonical names (added `_bounded_rename` with hash fallback). See "Pass 14" section. | 5 corpora pytest-green + ruff-clean; 0 régression réelle |

Detailed numbers after pass 10 (proto behaviour on the historical
single-corpus `/tmp/proto-fix/axm-audit-copy/`):

```
syntax errors:                  0
pytest collection:              1401 tests, 0 ERROR  (unchanged vs pass 9)
ruff regression vs baseline:    +0 (only pre-existing S607 remains)
idempotence (second dry-run):   0 ops planned
unit tests untouched:           411 → 411
test count delta:               -2 integration (= +2 e2e from offender)
layout flat:                    yes (0 nested files in tests/integration|e2e)
wall time on the corpus:        ~3 min (was 7 min 30 before import-index cache)
```

Three real-world surprises documented in the code (still applicable
after the split):

1. **Anvil's `rename=` param doesn't help cross-file collisions** — it
   validates target absence under the *original* name before applying
   the rename. The proto works around by renaming the symbol in source
   first (via `_rename_top_level_in_source` in `cst_rewrite.py`),
   then handing anvil a clean conflict-free move.

2. **`axm-audit`'s AST cache breaks after in-flight mutations** —
   calling `audit_project()` post-apply raises `FileNotFoundError` on
   cached paths. `collect_unfixable()` in `findings.py` swallows the
   exception defensively.

3. **`if TYPE_CHECKING:` imports are invisible to anvil** —
   `MockerFixture` imported only inside that block is treated as
   not-imported when the symbol using it (only via type annotation)
   is moved. `_backfill_missing_imports()` in `cst_rewrite.py` walks
   `if TYPE_CHECKING:` blocks and reproduces the wrapper at the
   target.

## Pass 11 (2026-05-16) — silent-test-loss + body-mismatch hardening

Pass 10 left a non-trivial regression budget on `axm-ast` (the largest
corpus): 64 failures + 7 errors pre-fix, 25 failures + 7 errors after
a first wave of helper-rename heuristics. Pass 11 closes the gap to
**0 failures, 0 errors, 1625 passed** (vs `1628 / 0 / 0` on the
unmodified repo — a 3-test delta attributed to runtime-conditional
skip parametrisation, not regressions).

Six concrete bug classes were identified and fixed (file references
updated to the post-split layout):

* **Bug 1 — `_make_pkg` signature drift across files.** SPLIT/MERGE
  moves a test depending on `_make_pkg(tmp_path, dict)` into a file
  whose local `_make_pkg(root, list, edges)` shadows it. Resolution:
  `_resolve_helper_conflicts()` in `layout_and_move.py` detects when
  a helper name exists in both source and target with different body
  hashes and renames the source-side helper (def + references) to
  `H__from_<stem>` before the anvil move. `shared_helpers="duplicate"`
  then copies cleanly. 11 renames triggered on axm-ast.

* **Bug 2 — `@pytest.mark.usefixtures("X")` invisible to anvil.**
  Anvil walks AST references on moving symbols, but marker arguments
  are string literals, not name references — so fixtures injected via
  marker stayed in source and disappeared when source was stripped.
  `_marker_fixtures_in_unit()` + `_collect_marker_fixtures_to_move()`
  in `tests_ast.py` now scan moving units for `usefixtures` markers
  and add the referenced fixtures to the move list when they're
  source-defined and not target-visible (including conftest chain).
  4 fixtures followed their dependents on axm-ast (`_mock_flows`,
  `_no_workspace`, `_mock_context`, `_patch_context`).

* **Bug 3 — `Path(__file__).parents[N]` drift after relocate.** A file
  moved from `tests/unit/core/test_X.py` (4-deep) to
  `tests/integration/test_X.py` (3-deep) keeps its
  `FIXTURES = Path(__file__).parents[2] / "fixtures"` constant — which
  now points to project root instead of `tests/`.
  `_patch_file_dunder_depth()` in `cst_rewrite.py` detects the depth
  delta from `_file_depth_from_project()` in `paths.py` and rewrites
  both surface forms (`parents[N]` subscript and `.parent.parent...`
  chains) via libcst. Wired into `_execute_relocate`, `_execute_rename`
  (`stages_execute.py`) and `_flatten_single_tier` (`layout_and_move.py`).
  7 patches on axm-ast.

* **Bug 4 — conftest fixture shadowing on MERGE.** When source has no
  local `rich_pkg` (relies on conftest's body) but target has a local
  `rich_pkg` with a different body, the moved tests bind to target's
  local at runtime and fail with `Symbol 'Greeter' not found`.
  Resolution extended `_resolve_helper_conflicts()` to also rename
  source's helper when target lacks it BUT a conftest on target's
  ancestor chain provides a fixture of the same name — preventing
  the anvil-duplicated helper from shadowing conftest.
  `_collect_conftest_fixtures()` (in `tests_ast.py`) walks the
  conftest chain.

* **Bug 6 — `_git_mv` silently overwrites destination.** The
  `shutil.move` fallback used when `git mv` refused (target exists)
  destroyed 25+ tests on axm-ast (`test_import_graph.py` was RENAME'd
  onto a `test_analyze_package.py` already populated by Stage 3 MERGE).
  `_git_mv()` in `io_primitives.py` now raises `FileExistsError` on
  pre-existing targets, and `_execute_relocate` / `_execute_rename`
  re-route through `_safe_move_units` instead — same pattern Stage 2
  SPLIT already used for cross-split collisions.

* **Bug 7 — promoted helper's dependencies left behind.** When
  `_extract_shared_helpers_in_tier()` (in `extract_helpers.py`)
  promotes a fixture (`pkg_with_tests`) to `tests/conftest.py`, its
  helper dependencies (`_write_pyproject`, `_write_src_module`,
  `_write_test_modules`) that already live in
  `tests/integration/_helpers.py` are not imported by the destination
  conftest. `_synth_import_from_helpers()` in `cst_rewrite.py` is a
  last-resort backfill in `_backfill_missing_imports()` that scans
  every `tests/<tier>/_helpers.py` for a top-level definition of the
  missing name and synthesises a
  `from tests.<tier>._helpers import <name>` statement.

### Validation matrix (axm-ast, after pass 11)

| Phase | Passed | Failed | Errors | Skipped | Ruff |
| ----- | ------ | ------ | ------ | ------- | ---- |
| Real repo (reference) | 1628 | 0 | 0 | 1 | 0 |
| Pass 10 baseline | 1529 | 64 | 7 | ? | 5 |
| Pass 11 final | **1625** | **0** | **0** | 4 | **0** |

The 3-test delta vs the real repo is runtime-conditional (skip
parametrisation depending on project path), not deterministic
regression. Ruff is clean.

### Pass 10 resolved blockers

All three pass-9 blockers (F401 / F811 / E501) are closed:

* **F401** (39 → 0) — `_collect_referenced_names` (`tests_ast.py`) is
  restricted to live top-level symbols (decorators, bases, annotations,
  reachable bodies). Dead branches and string-literal contents no
  longer trigger spurious backfills.
* **F811** (34 → 0) — `_dedupe_imports_cst` (`cst_rewrite.py`) tracks
  both `(module, name, asname)` triples *and* local binding names, so
  it catches shadow cases like `from a import X` followed by
  `from a.b import X` in addition to exact-duplicates.
* **E501** (213 → 0) — root cause was `ast.unparse` collapsing
  triple-quoted strings (typically `textwrap.dedent("""...""")`) into
  single-line literals. Fixed by writing through libcst, which
  preserves quote style and surrounding whitespace.

## Pass 12 (2026-05-16) — convergence fixes B1/B2/B3/B4

Triggered by the user noticing that even with pass 11 successful, the
post-fix `audit test_quality` did **not** reach FILE_NAMING = 0 +
PYRAMID_LEVEL = 0 on the 4 corpora — meaning the proto introduces
some findings while fixing others, and never settles. Four bug
classes addressed (file refs in the post-split layout):

* **B1 — pathological-AND-heterogeneous Test* classes**. A class with
  divergent canonicals AND a feature blocking flatten (`self.<attr>`,
  custom base, `__init__`) survives Stage 0 silently and breaks
  Stage 2 SPLIT (which can only route 4 of 5 canonical targets).
  Resolution: `_file_has_pathological_class()` (`tests_ast.py`) is a
  cheap pre-check used by `plan_naming` (`stages_plan.py`) to skip
  SPLIT planning for affected files; pathological cases are now
  surfaced as `collect_unfixable` (`findings.py`) entries pointing to
  `/scenario-rename` for manual review.

* **B2 — SPLIT/MERGE/RENAME planned for non-canonical tier paths**.
  Planner emitted ops for `tests/functional/test_X.py` but executor
  skipped them ("source not under tests/integration|e2e"). Resolution:
  filter in `plan_naming` (`stages_plan.py`) so SPLIT/COLLIDE/RENAME
  only ever land on canonical paths. Non-canonical files become an
  earlier-stage concern (B4 below).

* **B3 — pipeline ran a single pass**. Each stage's mutations can
  expose new findings (a SPLIT may produce small files reclassified
  as `unit` instead of `integration`; a RENAME may unblock a
  NAME_MISMATCH on a sibling). Resolution: `_run_one_iteration` +
  `MAX_ITERATIONS=6` loop in `pipeline.py`. Iteration stops early
  when a pass emits zero ops. **Known issue**: on axm-init the loop
  does NOT converge (still 20 PYRAMID_LEVEL findings + 1 false-
  positive FILE_NAMING after 6 iterations; pytest regresses 0 → 2
  fails). Hypothesis: SPLIT creates fine-grained files that the audit
  re-classifies in a way the next iteration cannot reconcile. To
  investigate in a future session.

* **B4 — `tests/functional/` and other non-canonical tier dirs
  ignored**. Files there are tier-less, so SPLIT/MERGE/RENAME silently
  refused them. Resolution: `relocate_non_canonical_tiers()` in
  `layout_and_move.py` runs as **Stage 0.5** (before Stage 1 RELOCATE)
  and moves every non-canonical tier file into `tests/integration/`.
  Subsequent stages then see only canonical paths. `CANONICAL_TIERS`
  set in `models.py` documents the allow-list (`unit`, `integration`,
  `e2e`).

### Validation matrix (axm-init, after pass 12 and after split)

| Phase | pytest | ruff | FILE_NAMING | PYRAMID_LEVEL | iterations |
|------|--------|------|-------------|---------------|------------|
| Real repo (reference) | 0 fail / 633 pass | clean | — | — | — |
| Pass 11 final | 0 fail / 664 pass | clean | 2 | 8 | 1 |
| Pass 12 final | 2 fail / 662 pass | clean | 1 (FP) + 1 unfixable | 20 | 6 (max) |
| After split (iso) | 2 fail / 662 pass | clean | 1 (FP) + 1 unfixable | 20 | 6 (max) |

The split commit changed file organisation only; the pipeline output is
byte-identical to pass 12. The two new fails (`test_detect_context__
project_context::TestDetectContext::test_detect[standalone|member]`)
and the PYRAMID regression 8 → 20 are pass-12 issues, not split issues.

## Pass 13 (2026-05-16) — B3 convergence resolution

Diagnosed by per-iteration instrumentation (`/tmp/diag_b3.py`,
ephemeral; see commit message for the script body). On axm-init the
oscillation was:

```
iter 1: relocate tests/integration/test_detect_context__project_context.py
        -> tests/unit/test_detect_context__project_context.py
iter 2: relocate tests/unit/test_detect_context__project_context.py
        -> tests/integration/test_detect_context__project_context.py
iter 3: relocate tests/integration/... -> tests/unit/...
...
```

Hypothesis (c) ("iteration cap too high") was wrong — the root cause is
mechanical: the file contains a `TestDetectContext::test_detect`
classified `integration` (real I/O + public import via
`request.getfixturevalue`) AND a `test_detect_context_falls_back_to_standalone`
classified `unit` (the rule sees `tmp_path` use but no real I/O on the
detected path). `plan_relocate` used to skip `cur == lvl` findings and
only count mismatches, so when the file lived in `integration/` it saw
"1 finding → unit" (unanimous in the filtered view), relocated, then
on the next pass saw "1 finding → integration" from the other test,
relocated back, forever.

* **Fix B3 — unanimity rule.** `plan_relocate` (`stages_plan.py`) now
  counts **every** test's target level (including `cur == lvl` ones).
  A file is relocated only when **all** tests agree on a single
  target distinct from the current tier. Mixed files (e.g.
  `tests/unit/core/test_identity.py` with 5 `unit` + 32 `integration`
  votes on axm-git) are left for manual `/scenario-rename` or hand
  splitting. This is conservative on purpose: the rule sacrifices
  some auto-resolution for guaranteed convergence.

Two collateral bugs surfaced while validating on axm-git:

* **Fix R — `_retier` ate the `.py` extension** for tests sitting at
  the `tests/` root (no tier subdir yet). For
  `tests/test_X.py` the function did `parts[1] = target_lvl` and
  returned `tests/<target_lvl>` (a directory), then
  `_safe_move_units` crashed with `IsADirectoryError` on
  `ast.parse(target.read_text())`. `paths.py:_retier` now branches on
  `len(parts) == 2`: inject the tier between `tests` and the file
  instead of substituting at index 1.

* **Fix G — `_git_mv` race.** When two ops in the same iteration both
  targeted the same destination, the second crashed in the
  `shutil.move` fallback with `shutil.Error("Destination path
  already exists")`. `io_primitives.py:_git_mv` now translates that
  to `FileExistsError`, and `_execute_relocate` / `_execute_rename`
  (`stages_execute.py`) catch it to re-route through a new
  `_reroute_through_safe_move` helper (factored from the two
  duplicated "target exists" branches). The pre-call `dst.exists()`
  check was also tightened from `is_file()` to `exists()` so a
  pre-existing directory at the target path no longer slips through.

### Validation matrix (pass 13, 5 corpora)

| Corpus | iter | crash | pytest after proto | régression réelle | ruff | Verdict |
|--------|------|-------|--------------------|--------------------|------|---------|
| axm-init | 1 | 0 | 662 pass / 2 baseline fails | 0 | clean | ✅ |
| axm-git  | 3 | 0 | 457 pass | 0 | clean | ✅ |
| axm-smelt | 2 | 0 | 298 pass | 0 | clean | ✅ |
| axm-ast | 3 | 0 | 1624 pass / 1 new fail | 1 (`test_broken_file`) | clean | 🟡 |
| axm-audit | 2 | 0 | 1448 pass / 23 fails (3 baseline + 20 new) | ~20 (helper-rename) | 2 E402/E501 | 🟠 |

"Unanimous-but-skipped" findings (where unanimity should have triggered
a relocate but didn't): **0** on init/git/smelt — the new rule is doing
the right thing on the cases it can handle. Residual `PYRAMID_LEVEL`
findings are **mixed files**, legitimately out of scope for the
deterministic proto.

## Pass 14 (2026-05-16) — collateral bug fixes from axm-audit validation

Pass 13 had only validated 4 corpora. Adding axm-audit (140 ops vs
122 for ast) revealed 4 latent bugs that the simpler corpora hadn't
exercised:

* **Fix D — dunder double-patch.** `_PatchChainOnce` (`cst_rewrite.py`)
  visits `.parent.parent.parent` *bottom-up*. The innermost `.parent`
  fired a "refusing to patch (would leave 0)" warning, the middle
  patched x2→x1, and the top patched x3→x2 — the chain ended up at
  x1 instead of x2 for a single `depth_delta = -1`. Fix: pre-pass
  collects the ids of every `.parent` Attribute that is the
  `.value` of an outer `.parent` (= non-top of its chain), and the
  transformer skips them. Critical detail: the id collection MUST
  happen after `_DunderPatcher` (libcst rebuilds nodes during any
  visit, even no-op transformations, so original `module` ids are
  stale by the time `_PatchChainOnce` runs on the new module).
  Affected ast — broke `tests/integration/test_parse_file.py`'s
  `FIXTURES` constant.

* **Fix H — helper-rename misses transitive references.**
  `_resolve_helper_conflicts` (`layout_and_move.py`) checked helper
  collisions only against names *directly* referenced by the moving
  units. axm-audit's `test_duplicate_tests_failed_populates_actionable_fields`
  doesn't reference `_write` directly — it consumes a fixture
  `duplicate_tests_project` which *itself* calls `_write`. Anvil
  moved the fixture alongside the test (via the marker-fixture
  follow-up), then deduplicated `_write` against target's same-named
  but body-different helper → moved tests bound to the wrong
  signature at runtime. Fix: extend `referenced` with a transitive
  closure — fixed-point iteration that walks names → source helpers
  → names-they-reference, until no new helpers appear. ~20 failures
  on axm-audit dropped to 0.

* **Fix E402 — split docstring placement.** SPLIT seeds a new file
  with `target.write_text('"""Split from ..."""\n')`, then anvil
  prepends imports before reaching the docstring. `_reorder_module_statements`
  in `cst_rewrite.py` used to treat any leading
  `ast.Expr/Constant/str` as part of the import "head" — so the
  docstring stayed *after* the imports, and ruff raised E402 on
  every subsequent import. Fix: detect the docstring as a separate
  statement (PEP 257: must be the very first body element to count
  as one) and unconditionally promote it to position 0 in the
  rewritten body.

* **Fix E501 — overlong renamed identifiers.** axm-audit had source
  files like `test_no_package_symbol_rule.py` (stem 22 chars). The
  collision-rename suffix `__from_no_package_symbol_rule` (29 chars)
  appended to an already-long test name pushed the def line past
  88 chars (e.g. 93 chars on `test_audit_test_quality_surfaces_new_rule__from_no_package_symbol_rule_in_audit_pipeline`).
  Fix: `_safe_move_units` in `layout_and_move.py` now uses a local
  `_bounded_rename` helper — if the full identifier would exceed
  73 chars (= 88 minus `def `, `(...)`, and a small margin), the
  stem-based suffix is replaced by a 6-char sha1 digest of the
  stem (`__from_<digest>`). Stem hashing keeps cross-source-file
  uniqueness; the verbose form is preferred when it fits.

### Validation matrix (pass 14, 5 corpora)

| Corpus | iter | crash | pytest | régression réelle | ruff |
|--------|------|-------|--------|--------------------|------|
| axm-init | 1 | 0 | 662 pass / 2 baseline fails | 0 | clean |
| axm-git  | 3 | 0 | 457 pass | 0 | clean |
| axm-smelt | 2 | 0 | 298 pass | 0 | clean |
| axm-ast | 3 | 0 | **1626 pass** / 3 skipped | 0 (was 1) | clean |
| axm-audit | 2 | 0 | **864 pass / 4 baseline fails** | 0 (was 20) | clean |

axm-ast regained 2 tests vs pass 13 because the dunder fix unblocked
a couple of fixture path resolutions besides `test_broken_file`.
axm-audit's 4 remaining fails are all baseline issues unrelated to
the proto (`test_rule_on_axm_audit_yields_zero_findings` cherche un
parent `axm-audit/` qui n'existe pas sous `/tmp/`; `test_findings_match_committed_baseline`
compare contre un fichier JSON figé pre-proto).

## Open issues (post-pass-14)

* **No known proto bugs.** All 5 corpora converge, pytest-green
  (modulo baseline fails), ruff-clean. Residual `PYRAMID_LEVEL`
  findings (init=1, smelt=3, audit=5, git=9, ast=21) are all mixed
  files legitimately out of scope for the deterministic proto —
  manual SPLIT or `/scenario-rename` is required.

* **`test_UNKNOWN.py` no longer surfaces in practice** — both
  `stages_plan.py` (SPLIT/RENAME planners) and `findings.py`
  (`_per_unit_canonical`) filter the name out at planning time.
  Originally an open issue; verified clean on the 5 corpora.

* **(legacy, kept for context) `test_UNKNOWN.py`** could appear when a file has no first-party
  signal AND no CLI invocation — but `NO_PACKAGE_SYMBOL` rule already
  flags that case. Either guard the proto against ever emitting that
  name, or accept it as a "to-be-deleted" marker and have the report
  prompt the user. (Pre-pass-12 nice-to-have, still open.)

* **Idempotence on dirty workspace** — current proto refuses nothing,
  trusts the user to start clean. A `--require-clean` flag that calls
  `git diff --quiet` would prevent foot-guns.

* **`--require-green` flag** — runs `pytest -q` before applying;
  refuses if tests are already broken, to ensure regression diff is
  attributable to the fix.

* **Better SPLIT-RENAME interplay** — when `_execute_split` finds
  that its anchor target already exists (cross-split collision), it
  routes through `_safe_move_units` instead of `_git_mv`. Works
  empirically but the path is convoluted. Refactor: stage 2 always
  emits both "create-new" and "merge-into-existing" ops in a single
  planning step.

* **Inline detector removal** — once AXM-1722 has stabilised, drop
  the remaining inlined helpers (currently `_func_canonical` in
  `findings.py` mirrors what FILE_NAMING does internally per-test).
  Replace with direct consumption of FILE_NAMING's per-test mapping
  if/when the rule exposes it.

## Productisation plan (AXM-1723)

The proto is **functionally correct AND ruff-clean** on the four
pass-11 corpora and now **converges deterministically** (pass 13) on a
fifth (axm-audit) — albeit with collateral helper-rename failures on
that corpus only. Once those are fixed, open the productisation ticket
with these acceptance criteria:

1. Move `fix_proto/` (12 modules) into `src/axm_audit/fix/`. The
   hexagonal split is already done — productisation is mostly
   `git mv` plus package metadata + tests.
2. Public API: `run_pipeline(project, *, apply, rules) -> PipelineReport`
   (already exposed via `fix_proto.run`).
3. Wire to the CLI: `axm-audit fix [--apply] [--rules=...]`. Default
   dry-run; mutate only on `--apply`.
4. Keep the libcst write path. ast is fine for read-only analysis.
5. Add `--require-clean` (refuse on `git diff --quiet` failure) and
   `--require-green` (`pytest -q` precheck) flags.
6. Test coverage: unit tests per module (most are now independently
   importable — `models`, `paths`, `io_primitives`, `tests_ast` are
   pure functions over stdlib types and trivial to unit-test). Add
   an integration test that runs the full pipeline on a fixture
   corpus and asserts ruff-clean output.

## Files of record

* `tuple_fix_proto.py` — CLI shim (70 LOC).
* `fix_proto/` — implementation (12 modules, ~3900 LOC).
* `tuple_naming_proto.py` — historical integration detector (May 2026).
* `tuple_naming_e2e_proto.py` — historical e2e CLI detector.
* `README.md`, `README_E2E.md`, `README_E2E_SESSION.md` — design docs.
* `README_FIX_PROTO.md` — **this file**, session note.

## Tickets in scope

* **AXM-1721** — `TEST_QUALITY_NO_PACKAGE_SYMBOL` rule (✅ merged).
* **AXM-1722** — `TEST_QUALITY_FILE_NAMING` rule (✅ merged).
* **AXM-1723** — `axm-audit --fix` deterministic applicator (**not
  created yet**). Will productise this proto. Body should reference
  this README and the ACs listed under "Productisation plan" above.
  B3 is no longer a blocker. Remaining pre-prod gates: fix the
  axm-audit helper-rename leak and the post-RENAME E402/E501 (see
  "Open issues").

## How to resume in a future conversation

1. `cd /Users/gabriel/Documents/Code/python/axm-workspaces/axm-forge/packages/axm-audit`
2. Read `scripts/test_orga/README_FIX_PROTO.md` (this file) first.
3. Read `scripts/test_orga/fix_proto/__init__.py` for the public API
   and the module index (each module's docstring explains its role).
4. Recreate the corpora at `/tmp/proto-fix-{init,git,smelt,ast}/` (see
   "Test corpus" section above) — they are **not** persisted.
5. To run: `python scripts/test_orga/tuple_fix_proto.py /tmp/proto-fix-init --apply`
   (the shim simply delegates to `fix_proto.run`).
6. Highest-priority open work: fix the helper-rename caller-leak on
   axm-audit (see "Open issues" — affects MERGE/COLLIDE intra-file
   helpers).

Stable commits to reset to in case of regression:

* `c2e185f` — pass 1, dry-run only, monolith.
* `4d4c6b6` — pass 3, post-collisions, pre-fixes, monolith.
* `4528dee` — pass 10, libcst write path, monolith.
* `293afb9` — pass 11, 4-corpora green, monolith.
* `(split commit)` — pass 12 + 12-module hexagonal split.
* `(pass-13 commit)` — B3 unanimity fix + `_retier` + `_git_mv` race,
  head of work.
