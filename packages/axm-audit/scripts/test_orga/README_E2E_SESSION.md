# E2E tuple-naming prototype — session report (May 2026)

Companion to `README.md` (integration tier, May session) and `README_E2E.md`
(e2e design). This document captures what the e2e proto produced once driven
across the workspace, the bugs in production rules it uncovered, the fixes
shipped in response, and what remains.

## Premise

`README_E2E.md` proposed an e2e equivalent of the integration tuple-naming
convention: count CLI invocation keys `(bin, sub)` instead of Python symbols,
emit `test_<a>-<b>.py`, K=2, filter by `[project.scripts]`. The proto bis
(`tuple_naming_e2e_proto.py`) was meant to validate the design on real
corpora before porting to a versioned rule.

It did more than that. Driving it across four packages of `axm-forge` —
`axm-audit`, `axm-init`, `axm-ast`, `axm-smelt` — exposed **three distinct
bugs in production rules** that were not the proto's target, and the session
became as much about fixing those as about validating the naming convention.

## What the proto v2 does

Same conceptual pipeline as v5 integration (`tuple_naming_proto.py`):
walk tests, transitive intra-module call closure, top-K=2, sort alphabetically,
emit canonical filename, compute per-file cohesion.

What's new vs v5:

- **`[project.scripts]` resolution** from `pyproject.toml` — only invocations
  of declared in-package binaries count toward the tuple. Plumbing (`git`,
  `uv`, `pip`, `pytest`, …) is filtered out by construction.
- **Permissive argv scan** — walks argv after peeling well-known runner
  prefixes (`uv run`, `python -m`, `poetry run`) and matches the first
  element that is either a declared script or the script's module-path form
  (`axm-audit` ↔ `axm_audit`). Non-resolvable elements (`str(tmp_path)`,
  fixtures, f-strings) are skipped, not fail-all.
- **Module-level string + list constant tracing** — `subprocess.run(cmd)`
  with `cmd = [...]` defined above resolves; `_UV_BIN = shutil.which("uv")`
  also handled (the dynamic part skips, the literal parts survive).
- **`CliRunner().invoke(app, [...])`** skeleton — maps `app` to the declared
  script via `[project.scripts]` entry-point modules. Resolves single-script
  packages; multi-script packages need per-import tracking (not implemented).
- **Three-status diagnosis** — `[E2E]`, `[INT]`, `[UNK]`:
  - `[E2E]` — tuple found, file has an in-package CLI tuple.
  - `[INT]` — no e2e tuple but file imports first-party symbols (passes the
    "two-criterion" rule of `README_E2E.md` §"What the rule looks like,
    extended" via the integration-style side). Recommendation: probably
    mis-tiered, belongs in `tests/integration/` rather than `tests/e2e/`.
  - `[UNK]` — no e2e tuple AND no first-party import. True rule violation:
    the test exercises neither the package's CLI nor its Python surface.
    Candidate for deletion or migration to a versioned rule of the package.
- **Inter-file collision (COLLIDE) metric** — for each canonical name
  emitted, how many distinct files would collapse to it. Side-product of
  the per-file cohesion: a file can be 100% cohesive intra-file yet share
  its canonical name with N siblings. This is the dominant pathology at
  the e2e tier, symmetrical to SPLIT (intra-file) at the integration tier.
- **Single-binary collapse** — when a package declares exactly one script
  (the workspace's default), the script name is stripped from the tuple
  prefix so `(axm-audit, audit)` emits `test_audit.py` rather than the
  noisier `test_axm_audit-audit.py`.
- **Cross-package summary table** at the end of the run, one line per
  package: `#Files E2E INT UNK COLLIDE% COH% SPLIT`.

## Verdict on the four packages (final run)

After all production fixes shipped this session (see below):

| Package    | #Files | E2E | INT | UNK | COLLIDE% | COH% | SPLIT |
|------------|-------:|----:|----:|----:|---------:|-----:|------:|
| axm-audit  |     10 |   9 |   1 |   0 |      89% |  93% |     0 |
| axm-init   |      5 |   2 |   3 |   0 |       0% | 100% |     0 |
| axm-ast    |     10 |   3 |   5 |   2 |       0% |  86% |     0 |
| axm-smelt  |      1 |   1 |   0 |   0 |       0% | 100% |     0 |

Two structural observations:

1. **At e2e, fragmentation is inter-file, not intra-file**. SPLIT (multiple
   tuples inside one file) is rare; COLLIDE (multiple files sharing one
   canonical name) is the actual signal. `axm-audit` saturates at 89% —
   eight files all classify under two CLI sub-commands (`audit`,
   `test-quality`). This is the e2e analogue of the SPLIT pathology that
   dominated the integration tier in May.

2. **A large share of "e2e" files are not e2e**. Of 26 total files audited,
   11 (42%) classify as `[INT]` or `[UNK]` under the proto's two-criterion
   verdict — they live in `tests/e2e/` under the strict AXM taxonomy
   ("subprocess present → e2e") but their **SUT is Python-level**, not the
   CLI binary. This finding is what triggered the production-rule fixes.

## Production-rule fixes shipped this session

The proto exposed three independent bugs in
`axm_audit.core.rules.test_quality.pyramid_level`. Each was implemented as
a standalone ticket; chronological order:

### Phase 1 — `classify_level` refinement

The pre-existing `classify_level` had `has_subprocess` as a binary
file-level signal: any `subprocess.*` in the AST → e2e. Plumbing subprocess
(`pip install`, `git init`, `uv venv`, `sys.executable -c "import ..."`,
`python -m`) misclassified entire files as e2e despite Python-level SUTs.

- `25acced` — **feat(axm-init)**: add `pyproject.wheel_doc_shipping` check
  (Check 38, weight 2). Auto-detects `docs/*.md` and verifies they're
  force-included in `[tool.hatch.build.targets.wheel.force-include]`.
- `be7462f` — Diataxis howto update for the new check.
- `5358c93` — **chore(axm-audit)**: delete `test_docs_packaging.py` (the
  invariant is now covered by the versioned `axm-init` rule, exactly the
  recipe of the May session's README).
- `71581d6` — **fix(axm-audit)** (ticket AXM-1718): detect in-package
  subprocess invocations. Adds `has_in_package_subprocess_invocation` with
  runner peeling, `python -m` aliasing, static argv reconstruction from
  module-level and intra-function string/list constants. 273 LOC + tests.
- `23968e7` — **fix(axm-audit)** (ticket AXM-1719): separate
  `has_subprocess` (raw diagnostic, kept) from `has_in_package_subprocess`
  (the tiering discriminator). Only the latter promotes to e2e; the former
  still surfaces for diagnostics elsewhere.
- `a03266b` — **test(axm-audit)** (ticket AXM-1720): three classifier
  validation tests — parametrized property grid, real-corpus differential
  scan of live packages, e2e CLI black-box of `axm-audit test-quality
  --json`. 366 LOC, AC1–AC4.

### Phase 2 — argv reconstruction follow-up

Post phase 1, 13 PYRAMID findings on `axm-audit` itself. Most were false
positives: legitimate e2e tests of `uv run axm-audit audit str(tmp_path) ...`
mis-classified as integration. Root cause in `_argv_from_list`: a single
non-resolvable element (a `str(tmp_path)` call) made the function return
`None` for the whole argv, killing the detection even though the prefix
`["uv", "run", "axm-audit", "audit"]` was perfectly resolved.

- `6b710da` — **fix(axm-audit)**: tolerate non-resolvable argv elements in
  pyramid classifier. `_argv_from_list` now returns `list[str]` and skips
  rather than fail-all. ~3 net lines, 1 regression unit test. Drops PYRAMID
  count 13 → 5 on `axm-audit`.

This was a direct port from the proto bis: the proto had been written
permissive from the start (returning `list[str | None]`), the production
port had tightened it. Aligning them resolved the regression.

### Phase 3 — closure walk follow-up

Post phase 2, 5 remaining PYRAMID findings. Two were faux positifs on
`test_pyramid_findings_unchanged.py`: a legitimate e2e test whose
`subprocess.run([sys.executable, "-m", "axm_audit", ...])` lived inside a
module-level helper `_run_test_quality`, called by the test. The
production rule scanned only `ast.walk(test_node)`, missing the helper.

- `fb27da4` — **fix(axm-audit)**: walk module-level helpers in pyramid
  subprocess detection. Ports `_closure_nodes_for_test` from v5
  (`tuple_naming_proto.py:177-229`) into the production scanner. ~40 net
  LOC, 1 regression unit test. Drops PYRAMID count 5 → 3 on `axm-audit`.

### Phase 4 — relocation of legitimate residual findings

Three PYRAMID findings remained, all genuine. Two files needed action:

- `7e1d64f` — **test(axm-audit)**: relocate
  `test_coverage_rule_excludes_main.py` to integration. Whole-file move,
  the docstring + marker already declared integration; only the physical
  location lagged. 1 test, 0 line changes besides `git mv`.
- `16b66aa` — **test(axm-audit)**: split deprecate-mode tests across
  integration and e2e. Anvil-based CST split: 2 mocked unit-style tests
  (`TestDeprecatedMode`) moved to `tests/integration/`, 1 subprocess CLI
  test (`TestCliNoModeFlag`) stayed in `tests/e2e/`. Anvil pruned dead
  imports automatically.

### Workspace cleanup (parallel during the session)

- `axm-ast` — 20+ test files relocated across pyramid levels (commits
  `edda4da`, `5f623e4`, `ea9740e`, `6fdd268`, `3706b62`, and earlier
  series). The package now has **zero files in `tests/e2e/`**, all
  faux-e2e correctly demoted to unit/integration after the rule fixes.
- `axm-init` — `test_cli.py` extracted, `test_cli_subcommands_end_to_end`
  shrunk from 41 tests to its e2e core, several integration files added
  (`test_changelog_gitcliff_requirement.py`, `test_cli_workspace_scaffold_subcommands.py`, …).

## Final state

| Package    | PYRAMID findings | Grade | Notes |
|------------|-----------------:|:-----:|-------|
| axm-audit  | 0 ✅              | A 🏆  | score 90/100 |
| axm-init   | 0 ✅              | —     | — |
| axm-ast    | 0 ✅              | —     | tests/e2e/ now empty |
| axm-smelt  | 0 ✅              | —     | singleton, unchanged |

All four packages audited during the session land at zero `TEST_QUALITY_PYRAMID_LEVEL`
mismatches after the four fix commits and the two relocation commits.

## What the proto v2 taught us about the rule design

Three lessons portable to the as-yet-unwritten `TEST_QUALITY_NO_PACKAGE_SYMBOL`:

1. **The "two-criterion" rule from `README_E2E.md` is right.** A test in
   `tests/e2e/` should pass iff it (a) invokes the in-package CLI in
   subprocess, OR (b) imports first-party symbols. The proto's `[INT]`
   status is exactly the (a)-fail-(b)-pass case — empirically real, not
   theoretical: 9 files across 3 packages.

2. **The (a)-fail-(b)-pass case is structurally distinct from the
   (a)-fail-(b)-fail case.** The first is mis-tiered (recommend
   `tests/integration/`); the second is the genuine rule violation
   (candidate for deletion or migration to an `axm-init`-style versioned
   rule). The proto should keep them in distinct sections in any output;
   a flat "UNKNOWN" verdict conflates two very different actions.

3. **At e2e, the dominant pathology is COLLIDE (inter-file), not SPLIT
   (intra-file).** This is the opposite of the integration tier. The
   metric to surface in any production tool is the share of E2E-named
   files in collision groups, not just per-file cohesion. `axm-audit`'s
   89% COLLIDE is a real structural finding: it suggests 8 of 9 files
   could merge under two scenario-named parent files (`test_audit.py`,
   `test_test_quality.py`) without losing coverage.

## What remains

Three follow-ups, by decreasing priority. None is blocking; the session's
load-bearing work is shipped.

### 1. Port the rule `TEST_QUALITY_NO_PACKAGE_SYMBOL`

The original target of the May integration session and the `README_E2E.md`
design. With the pyramid classifier now correct, this rule can be written
on a clean substrate:

- Reuse `axm_audit.core.rules.test_quality._shared` helpers
  (`iter_test_files`, `analyze_imports`, `_collect_fixtures`).
- Port the proto's `[project.scripts]` resolution and permissive argv scan
  (now also in `pyramid_level.py` — single source of truth?).
- Emit findings at WARNING severity (per `README.md` §"Proposed rule").
- Distinguish the two failure modes:
  - `(a)-fail-(b)-pass` → recommend relocation to integration (or merge
    with `TEST_QUALITY_PYRAMID_LEVEL`, which already covers this; check
    for overlap before duplicating).
  - `(a)-fail-(b)-fail` → recommend deletion or versioned-rule migration.

This is also where the inter-file COLLIDE metric belongs, possibly as a
sibling rule `TEST_QUALITY_FILE_COHESION` (mentioned as Open Work at the
bottom of `README.md`).

### 2. Resolve remaining `[INT]` flags in axm-ast

Five files in `axm-ast/tests/e2e/` still pass `[INT]` under the proto's
two-criterion check. These were not in the pyramid mis-tier scope (the
classifier now agrees they're e2e under the strict taxonomy because their
subprocess is in-package, even though the proto sees no tuple). Inspect
manually:

- `test_callers_typecheck.py` (1 test, dyn-skip)
- `test_impact_under_optimize.py` (1 test, dyn-skip)
- and the three other `[INT]` files

`dyn-skip` indicates argv non-resolvable from constants alone. Either the
test legitimately uses fixture-injected arguments (port the v5 fixture
resolution into the proto, see point 3), or it's structurally similar to
the relocated `test_audit_test_deprecate_mode.py` and needs splitting.

### 3. Optional proto enhancements

If `TEST_QUALITY_NO_PACKAGE_SYMBOL` is delayed, the proto can grow:

- **Fixture resolution** — port `_collect_fixtures` + `_resolve_fixture_symbol`
  from v5 (`tuple_naming_proto.py:237-302`). Catches cases where a fixture
  performs the CLI invocation and yields its result; tests consuming the
  fixture would otherwise emit no tuple.
- **`dyn-skip` diagnostic table** — for each file with dyn-skip > 0, dump
  the unresolved AST node types. Currently this signal exists in aggregate
  but doesn't tell you why argv didn't resolve.
- **Multi-binary support for `CliRunner`** — the current skeleton handles
  single-script packages only; multi-script packages would need per-import
  tracking from `[project.scripts]` entries to `app` symbol bindings in
  the test module. Low priority (no multi-script package in the workspace
  today).

None of these is required for the rule port; they're proto-only quality
of life. The rule port can pull v5's fixture resolution directly without
ever touching the proto.

## Files of record

- `tuple_naming_e2e_proto.py` — the proto v2 itself, ~570 LOC.
- `README.md` — integration tier session report (May 2026).
- `README_E2E.md` — original e2e design proposal.
- `README_E2E_SESSION.md` — this file.

## Tickets closed this session

- AXM-1715 — `axm-init wheel-doc shipping` rule.
- AXM-1718 — in-package subprocess detection in `pyramid_level`.
- AXM-1719 — separate raw `has_subprocess` from `has_in_package_subprocess`.
- AXM-1720 — classifier validation tests on known false e2e files.

Two follow-up fixes shipped without dedicated tickets (small scope,
direct continuation of AXM-1718–1720): `6b710da` (argv tolerance) and
`fb27da4` (closure walk).
