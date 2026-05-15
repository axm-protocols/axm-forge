# Test organisation diagnostics

Prototype tool that derives a **canonical tuple-based filename** for every
integration test file by extracting the package symbols each test actually
exercises (via static AST + intra-module call closure + pytest fixture
resolution).

The script is intentionally a single-file prototype: it explores ideas
before committing to a versioned rule in `axm_audit`. Once the design
stabilises, the detection logic migrates into a proper
`TEST_QUALITY_NO_PACKAGE_SYMBOL` rule (see "Proposed rule" below).

## What the tool does

For each `tests/integration/test_*.py` file under a target package:

1. Collect every name imported from `PACKAGE` (top-level + inside helpers).
2. For each test function (module-level or method of a `Test*` class),
   walk the **intra-module call closure** — the test body, any module-level
   helper it transitively calls, and any module-level class it references.
3. Resolve `@pytest.fixture` parameters: if a fixture's return annotation
   or `return X(...)` expression yields a known package symbol, count that
   symbol once for every reference to the fixture name in the test body.
4. Rank symbols by usage frequency, take the top-K (K=2 by default), sort
   alphabetically, and emit `test_<s1>-<s2>.py` (snake_case, dash-separated).
5. Aggregate per file: union top-K across the file's tests gives the
   proposed filename; cohesion = share of tests whose own tuple equals
   the union.

### Naming convention

| Tuple size | Filename                       | Example                                |
|-----------:|--------------------------------|----------------------------------------|
|          1 | `test_<sym>.py`                | `test_mirror_rule.py`                  |
|          2 | `test_<s1>-<s2>.py`            | `test_finding-triage.py`               |
|          0 | `test_UNKNOWN.py` (pathology)  | flagged for review                     |

PascalCase symbols are converted to snake_case (`ComplexityRule` →
`complexity_rule`). Symbols inside a tuple are sorted alphabetically so
ordering is deterministic. The dash separator (instead of `__`) avoids
the dunder-like look of `test__a__b.py` and is unambiguous because Python
symbols never contain `-`.

For tests at `tests/unit/`, the K=1 case (`test_<source_module>.py`)
collapses to the canonical mirror layout already mandated by AXM.

## Reading the output

```
CURRENT                                          #T   COH  PROPOSED
test_mirror_rule.py                              12  100%  test_mirror_rule.py
test_actionable_findings.py                       8   0%   test_private_imports_rule-pyramid_level_rule.py *S*
test_isolation.py                                 1   0%   test_UNKNOWN.py
```

- **`#T`** — number of tests in the file
- **`COH`** — share of tests whose individual tuple equals the file's
  union top-K. 100% = perfectly cohesive; <50% = file likely mixes
  intents.
- **`PROPOSED`** — canonical filename based on the union top-2 tuple.
  `test_UNKNOWN.py` means the file exercises zero package symbol.
- **`*S*`** — file is flagged SPLIT: at least two tests disagree on the
  top-K tuple, so decomposing the file along tuple boundaries would
  produce cohesive sub-files.

## What we learned (May 2026 session)

The tool was driven across five packages of the `axm-forge` workspace.
Same script, same parameters, very different verdicts:

| Package       | Files | Cohesion K=2 | UNKNOWN start | UNKNOWN final | SPLIT |
|---------------|------:|-------------:|--------------:|--------------:|------:|
| `axm-smelt`   |     4 |         100% |             0 |             0 |    0% |
| `axm-git`     |     3 |         100% |             0 |             0 |    0% |
| `axm-audit`   |   101 |          71% |             9 |             0 |   35% |
| `axm-ast`     |    75 |          64% |             2 |             0 |   44% |
| `axm-init`    |    38 |          38% |             7 |             0 |   68% |

Three confirmed observations from running across the matrix:

1. **K=2 is the right tuple size.** K=3 was evaluated on every package
   and dropped average cohesion by 2–13 points each time, without
   gaining structural insight. Adding a third symbol simply picks up
   ambient noise: any extra symbol referenced by one test but not its
   siblings fragments the per-file cohesion score with no useful
   discrimination in return. K=3 occasionally resolves a collision but
   only by hiding a legitimate aggregation signal.

2. **UNKNOWN = "test of an artefact, not behaviour" is a robust
   pattern.** Of the 18 initial UNKNOWNs identified across the matrix,
   12 turned out to be detection limits of the prototype itself — fixed
   in later versions (closure of helpers, fixture resolution). The 6
   genuine UNKNOWNs that remained were **all** found to be tests that
   greped/parsed an artefact (manifest, doc, template) without
   exercising the package, and all merited deletion. **100% of true
   UNKNOWNs were bad tests.** That is strong enough to support a rule.

3. **The convention is not universally valuable.** On packages with
   ≥70% cohesion (`axm-git`, `axm-smelt`, `axm-audit`), human-chosen
   scenario names (`test_identity_roundtrip.py`,
   `test_aggressive_preset_uses_new_name.py`) carry more information
   than the canonical tuple names and should be kept. Below 70%, the
   canonical tuple reveals real fragmentation that scenario naming
   masks — `axm-init` and `axm-ast` both contain files of 30–60 tests
   that are dossiers déguisés en fichiers. The tuple framework is best
   read as a **diagnostic lens** (a structural-health metric) before
   any naming change.

## Outcomes of the session

11 test files (~55 tests total) deleted across three packages, each
identified mechanically by the UNKNOWN signal, validated by hand, and
removed in a single commit per package with the same root cause: a
pytest test asserting on a static artefact (hardcoded list copied from
a manifest, regex match on a doc, string grep on a template, AST walk
of a source file) instead of exercising package behaviour.

| Commit    | Package      | Files | Pattern                                |
|-----------|--------------|------:|----------------------------------------|
| `df1bfc6` | `axm-audit`  |     1 | manifest duplicated as test data       |
| `46ac717` | `axm-audit`  |     3 | CC budgets / doc-structure greps       |
| `3269c53` | `axm-init`   |     5 | template-content greps                 |
| `cd8f319` | `axm-init`   |     1 | template Python-validity check         |
| `92d5c65` | `axm-ast`    |     1 | source-grep "no assert in production"  |

The recurring fix architecturally is **not** to migrate the test to a
different location: it is to express the invariant as a versioned rule
of the package itself, so the package can self-apply on its own
templates / source / config. `axm-init check` already covers ~25 of
these invariants for downstream projects but did not previously apply
to its own templates — that gap is what the deleted tests were trying
to fill by hand.

## Proposed rule: `TEST_QUALITY_NO_PACKAGE_SYMBOL`

The findings justify a new rule in
`axm_audit/core/rules/test_quality/`, alongside `pyramid_level`,
`tautology`, `private_imports`, etc.

**Trigger.** A test function (top-level or method of a `Test*` class)
in `tests/integration/` or `tests/e2e/` that:

- imports nothing from any first-party package, OR
- imports first-party symbols but the intra-module closure (test body +
  helpers it transitively calls + fixtures it consumes) references zero
  of them.

**Severity.** `WARNING`. Unlike `private_imports` (ERROR), an UNKNOWN
test can occasionally be legitimate (formal property check on a
distributable artefact), so the rule should not block — it should
prompt review.

**Score impact.** Small penalty (e.g. 2 points per finding, vs 5 for
`private_imports`), capped to leave room for the larger
`pyramid_level` and `tautology` penalties.

**Fix hint.** `Express the invariant as a versioned rule of the
package under test (so the package self-applies on its own artefacts),
or move the check to a doc/packaging linter outside the pytest suite.`

**Reuses existing helpers.** The `_shared` module in
`test_quality/` already exposes `iter_test_files`, `get_pkg_prefixes`,
`_collect_fixtures`, `_is_pytest_fixture`, `analyze_imports`. The new
rule should import these rather than duplicate the logic the prototype
has. The closure-walk and the symbol-counting can stay in the new
rule's own file (similar in size to `private_imports.py`).

**Exemptions.**

- Property-based tests that call only formal checkers (`compile`,
  `ast.parse`, `json.loads`, `yaml.safe_load`, `tomllib.loads`) and
  no hardcoded content assertions. Realistic policy is to *not*
  whitelist these and let the user resolve them by migrating to a
  versioned rule of the target package — every legitimate-looking
  formal-check test we reviewed in this session turned out to be
  redundant with an existing or trivially-extendable rule.
- Explicit `@pytest.mark.no_package_symbol_ok` marker on the test or
  module, for the residual cases.

**Where the rule complements existing test-quality rules.**

| Existing rule                     | Catches                                       | Gap this rule fills                       |
|-----------------------------------|-----------------------------------------------|-------------------------------------------|
| `TEST_QUALITY_PYRAMID_LEVEL`      | wrong directory (I/O, subprocess signals)     | doesn't look at what symbol is exercised  |
| `TEST_QUALITY_PRIVATE_IMPORTS`    | tests reaching into `_private` symbols        | flags coupling, not absence of coupling   |
| `TEST_QUALITY_TAUTOLOGY`          | empty/self-comparing/mock-echo assertions     | targets assertion shape, not what's hit   |
| `TEST_QUALITY_DUPLICATE_TESTS`    | tests redundant with each other               | independent of single-test validity       |
| **`TEST_QUALITY_NO_PACKAGE_SYMBOL`** *(new)* | tests that exercise no package symbol         |                                            |

Together these five rules form a coherent stack: a test must be in the
right tier (pyramid_level), not couple via private imports
(private_imports), make a real assertion (tautology), not duplicate
others (duplicate_tests), **and** actually touch the package
(no_package_symbol). Each rule attacks a distinct pathology of
"passing for the wrong reasons."

## Usage

Edit the two constants at the top of `tuple_naming_proto.py`:

```python
PACKAGE = "axm_audit"
TESTS_DIR = Path(".../packages/axm-audit/tests/integration")
```

Then:

```
uv run --python 3.12 python tuple_naming_proto.py
```

Output sections:

- **Per-file table** with current name, #tests, cohesion, proposed name
- **K=2 vs K=3 comparison** — keep K=2; the comparison is there to let
  you re-verify the verdict on a new corpus
- **UNKNOWN files** — every file with empty union is listed for review
- **Drill-down on top-5 largest files** — shows the per-tuple breakdown,
  which is where SPLIT files reveal their latent sub-files

## Open work

- **`hooks/` and other nested integration subdirs.** Some packages
  (`axm-ast`, `axm-git`) put integration tests under
  `tests/integration/<subdir>/`. AXM's CLAUDE.md states the integration
  tree should be flat; the prototype uses `rglob` so it sees those
  files, but the layout itself is a separate finding worth surfacing
  via `TEST_QUALITY_PYRAMID_LEVEL` or a sibling rule.
- **One last UNKNOWN was not resolved by fixture inference**
  (`test_dependency_text_format.py` on a pre-cleanup `axm-audit`).
  The fix landed in v5 of the prototype; the algorithm now resolves
  fixture-typed parameters via the fixture's return annotation or
  `return X(...)` body. Worth porting verbatim into the production rule.
- **Cohesion as its own metric.** The 70% threshold separating
  "human names better" from "tuple reveals fragmentation" is empirical.
  Worth tracking it as a `TEST_QUALITY_FILE_COHESION` warning (distinct
  from this rule) once the no-package-symbol rule is in place.
