# `tuple_fix_proto.py` — session note (2026-05-16)

Companion to `tuple_naming_proto.py` (integration tuple detector, May 2026)
and `tuple_naming_e2e_proto.py` (e2e CLI tuple detector). This proto is
the **deterministic applicator** that consumes findings from the two new
versioned rules (AXM-1721 `TEST_QUALITY_NO_PACKAGE_SYMBOL`, AXM-1722
`TEST_QUALITY_FILE_NAMING`) plus the existing `TEST_QUALITY_PYRAMID_LEVEL`,
and applies a 5-stage pipeline that physically moves / splits / merges /
renames test files using `axm-anvil.move_symbols` for CST-correct edits.

The intent is to produce a `axm-audit --fix` binary (ticket AXM-1723, not
yet created — see "What's next") that runs in dry-run by default and
mutates only on `--apply`.

## Pipeline architecture

```
0. FLATTEN     class Test* with heterogeneous tuples → top-level funcs
1. RELOCATE    PYRAMID_LEVEL mismatches → git mv across tiers
   ─ re-audit (paths have changed) ─
2. SPLIT       FILE_NAMING SPLIT → axm-anvil moves units to canonical targets
   ─ re-plan ─
3. MERGE       FILE_NAMING COLLIDE → axm-anvil moves units to anchor
   ─ re-plan ─
4. RENAME      FILE_NAMING NAME_MISMATCH → git mv to canonical name
```

`NO_PACKAGE_SYMBOL` findings are **out of pipeline** — the verdict is
context-dependent (legitimate formal check vs. candidate for deletion),
not auto-fixable. They appear in a separate report section pointing the
user to `/scenario-rename` or manual inspection.

The `NON_DETERMINISTIC_RULES` frozenset documents this boundary in code,
with the rationale in a comment.

## Test corpus

The proto was validated against a copy of `axm-audit` at
`/tmp/proto-fix/axm-audit-copy/` (git-init'd locally; HEAD =
`4941a1f test: inject RELOCATE offender`). The copy is preserved between
runs via `git reset --hard HEAD -q && git clean -qfdx` to allow
idempotence and regression checks across iterations.

To recreate after a reboot:

```bash
cp -R /Users/gabriel/Documents/Code/python/axm-workspaces/axm-forge/packages/axm-audit /tmp/proto-fix/axm-audit-copy
cd /tmp/proto-fix/axm-audit-copy && rm -rf .git && git init -q && git add -A
git commit -q -m "baseline"
# Then inject the synthetic RELOCATE offender (see Pass 1 below)
```

## What we did — 10 iteration passes

Each pass = one full `--apply` of the proto on the corpus, followed by
inspection of the result. The git commits are in
`packages/axm-audit/` of the main repo, not the `/tmp` copy.

| Pass | Commit | Key change | Verdict |
|------|--------|-----------|---------|
| 1 | `c2e185f` | Initial proto, dry-run only, detector inlined | Plan looks coherent |
| 2 | `0b921ac` | First full apply, collisions handled by suffix `__from_<stem>` | 122 ops applied, idempotent, but 197 integration tests vanished |
| 3 | `4d4c6b6` | Inter-stage **re-plan**: stages 2-4 see post-mutation paths via re-call to `plan_naming()` | Test count restored (1050 → 1050 via AST); idempotent |
| 4 | (uncommitted) | `_safe_filename()` substitutes `-` → `__` in canonical paths to satisfy PEP8 module-name rules; `_reorder_module_statements()` topological sort respecting decorators + class bases; `_backfill_missing_imports()` recovers imports lost across moves (with TYPE_CHECKING wrapper preservation and cross-file fallback via `_scan_tests_for_import()`) | Pytest collection succeeds with 1401 tests, 0 ERROR; F821 = 0; N999 = 0 |
| 10 | this commit | **Full migration to libcst for mutating helpers**: `_delete_function_from_source`, `_rename_top_level_in_source`, `_flatten_class_to_top_level`, `_reorder_module_statements`, `_backfill_missing_imports`, `_dedupe_imports` all write through libcst (preserves triple-quoted strings, comments, blank lines). ast remains for read-only analysis. Global import-index cache replaces per-name re-walk. Local-binding shadow detection in dedup. Minimal split-docstring template. | **Ruff 1 → 1** (zero regression; sole survivor is the synthetic `S607` offender from baseline) |

Detailed numbers after pass 10 (current state of the proto):

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

Three real-world surprises documented in the code:

1. **Anvil's `rename=` param doesn't help cross-file collisions** — it
   validates target absence under the *original* name before applying
   the rename. The proto works around by renaming the symbol in source
   first (via AST rewrite in `_rename_top_level_in_source`), then handing
   anvil a clean conflict-free move.

2. **`axm-audit`'s AST cache breaks after in-flight mutations** — calling
   `audit_project()` post-apply raises `FileNotFoundError` on cached
   paths. `collect_unfixable()` swallows the exception defensively.

3. **`if TYPE_CHECKING:` imports are invisible to anvil** — `MockerFixture`
   imported only inside that block is treated as not-imported when the
   symbol using it (only via type annotation) is moved.
   `_backfill_missing_imports()` walks `if TYPE_CHECKING:` blocks and
   reproduces the wrapper at the target.

## What remains — DO NOT delete the proto until done

### Pass 10 resolved blockers

All three pass-9 blockers (F401 / F811 / E501) are closed:

* **F401** (39 → 0) — `_collect_referenced_names` is restricted to
  live top-level symbols (decorators, bases, annotations, reachable
  bodies). Dead branches and string-literal contents no longer
  trigger spurious backfills.
* **F811** (34 → 0) — `_dedupe_imports_cst` tracks both
  `(module, name, asname)` triples *and* local binding names, so it
  catches shadow cases like `from a import X` followed by
  `from a.b import X` in addition to exact-duplicates.
* **E501** (213 → 0) — root cause was `ast.unparse` collapsing
  triple-quoted strings (typically `textwrap.dedent("""...""")`)
  into single-line literals. Fixed by writing through libcst, which
  preserves quote style and surrounding whitespace.

### Nice to have (post-MVP)

* **`test_UNKNOWN.py`** can appear when a file has no first-party
  signal AND no CLI invocation — but `NO_PACKAGE_SYMBOL` rule already
  flags that case. Either guard the proto against ever emitting that
  name, or accept it as a "to-be-deleted" marker and have the report
  prompt the user.

* **Idempotence on dirty workspace** — current proto refuses nothing,
  trusts the user to start clean. A `--require-clean` flag that calls
  `git diff --quiet` would prevent foot-guns.

* **`--require-green` flag** — runs `pytest -q` before applying;
  refuses if tests are already broken, to ensure regression diff is
  attributable to the fix.

* **Better SPLIT-RENAME interplay** — when `_execute_split` finds that
  its anchor target already exists (cross-split collision), it routes
  through `_safe_move_units` instead of `_git_mv`. Works empirically
  but the path is convoluted. Refactor: stage 2 always emits both
  "create-new" and "merge-into-existing" ops in a single planning step.

* **Inline detector removal** — once AXM-1722 has stabilised, drop the
  remaining inlined helpers (currently the proto reuses `_shared`
  but a few helpers still re-implement detection logic, e.g.
  `_func_canonical` mirrors what FILE_NAMING does internally per-test).
  Replace with direct consumption of FILE_NAMING's per-test mapping
  if/when the rule exposes it.

## Productisation plan (next session)

The proto is now **functionally correct AND ruff-clean** (1 → 1, the
sole survivor is the pre-existing `S607` baseline). It is ready to be
productised as `axm-audit --fix` (ticket AXM-1723).

Open the ticket with these acceptance criteria:

1. Move the proto's logic into `src/axm_audit/fix/` with a typed public
   API (`run_pipeline(project, *, apply, rules) -> PipelineReport`).
2. Wire to the CLI: `axm-audit fix [--apply] [--rules=...]`. Default
   dry-run; mutate only on `--apply`.
3. Keep the libcst write path. ast is fine for read-only analysis.
4. Add `--require-clean` (refuse on `git diff --quiet` failure) and
   `--require-green` (`pytest -q` precheck) flags.
5. Test coverage: unit tests for each helper (rename, flatten,
   reorder, backfill, dedup), integration test that runs the full
   pipeline on a fixture corpus and asserts ruff-clean output.

## Files of record

* `tuple_fix_proto.py` — the proto, ~1700 LOC after pass 10 (libcst write path).
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

## How to resume in a future conversation

1. `cd /Users/gabriel/Documents/Code/python/axm-workspaces/axm-forge/packages/axm-audit`
2. Read `scripts/test_orga/README_FIX_PROTO.md` (this file) first.
3. Recreate the `/tmp/proto-fix/axm-audit-copy/` corpus (instructions
   in "Test corpus" section above) — it is **not** persisted.
4. Invoke `/plan-tickets` with this README as input to open AXM-1723.

Stable commits to reset to in case of regression: `4d4c6b6` (pass 3,
post-collisions, pre-fixes) and `c2e185f` (pass 1, dry-run only).
Pass 10 (this commit) is the current head of the work.
