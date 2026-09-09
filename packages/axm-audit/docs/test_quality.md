# Test Quality Rules

The `test_quality` category surfaces rules that reason about the **test tree
itself** — what it imports, how it asserts, which fixtures do real I/O. Unlike
`testing` (which measures the Python suite and coverage), `test_quality` rules guard against
brittleness: tests that couple to implementation details, tautological
asserts, or mock patterns that drift from production behavior.

## CLI

```bash
axm audit [PATH] --json-output --category test_quality
```

Runs the `test_quality` category through the `audit` AXMTool. The unified CLI
prints JSON with `--json-output`, and compact text otherwise. The data
includes evaluated `TEST_QUALITY_*` rules; the `axm_call` façade exposes text only. The command
exits non-zero for a tool error, but reported quality failures do not by
themselves change its exit code. See the [CLI
reference](reference/cli.md) for details.

Each pyramid mismatch line in the compact renderer shows the coarse
`reason` and, when present, the deciding `io_signals` that drove the
classification, appended as a compact, deterministically-ordered
fragment (e.g. `signals: fixture:db_session, tmp_path->open`). The
fragment is omitted entirely when no signals were recorded.

## Private Imports

The examples below illustrate triage shapes; historical corpus paths are
not a guarantee that those files remain in the current workspaces.

**Rule ID**: `TEST_QUALITY_PRIVATE_IMPORTS`
**Class**: `axm_audit.core.rules.test_quality.PrivateImportsRule`
**Severity**: `ERROR`
**Score**: `max(0, 100 - n_violations * 5)`

Flags `tests/**/test_*.py` imports of `_prefixed` symbols from first-party
packages. Importing private helpers couples the test suite to implementation
details, so a simple refactor of a private function turns into a multi-file
chore.

### DELETE / REFACTOR / PROMOTE triage

Every private-import finding falls into one of three buckets — the same
taxonomy used by the original `DECISION_PRIVATE_IMPORTS.md` roadmap note:

| Bucket | Meaning | AXM example |
| -- | -- | -- |
| **DELETE** | The test asserts a private helper directly; the scenario is already covered by a public-API test. Drop the redundant test. | `example/tests/unit/test_normalize.py::test_normalize` — removed after `test_hook_run.py` covered the same path via the public a public entry point entry point. |
| **REFACTOR** | The test is valuable but reaches through a private surface. Replace the private symbol with a fixture, factory, or public seam. | `axm-audit/tests/unit/core/test_coupling_scoring.py` stopped importing `_compute_fan_out` and now drives scoring via a `CouplingMetricRule` instance. |
| **PROMOTE** | The private helper is de-facto public; the right fix is to drop the `_` prefix and export it. | `axm-nexus/tests/test_registry.py` triggered promoting `_ResourceCatalog._load` to `ResourceCatalog.load` plus an `__all__` entry. |

### What it flags

The implementation also resolves private attribute accesses through first-party
imports and class instances when their kind can be established. Findings include
`access_kind` (`import` or `attribute`); unresolved attributes are skipped.

For every test file the rule walks `ast.ImportFrom` nodes whose module starts
with a package under `src/`. Each imported symbol is inspected:

| Symbol shape      | Flagged? | Notes                                          |
| ----------------- | -------- | ---------------------------------------------- |
| `_private`        | yes      | Classified via `axm_ast.extract_module_info`   |
| `_PrivateClass`   | yes      | Kind = `class`                                 |
| `_UPPER_CASE`     | no¹      | `_[A-Z][A-Z0-9_]+` matches — constants only    |
| `__dunder__`      | no       | Always skipped                                 |
| public name       | no       | Not `_`-prefixed                               |

¹ Set `include_constants=True` on the rule to surface `_UPPER_CASE` constants
as well. Each finding records `test_file`, `line`, `import_module`,
`private_symbol` and a `symbol_kind` (`function`, `class`, `constant`,
`variable`, `unknown`).

### Same-package submodule exemption

Imports of `_prefixed` *modules* (not symbols) from the same top-level
first-party package as the test file are not flagged. For example, in a
package `mypkg`, `from mypkg.sub import _helper` resolves to the submodule
`mypkg/sub/_helper.py` and is allowed when the test lives under that
package's test tree. Cross-package imports of private submodules
(e.g. `pkg_b` test importing `from pkg_a import _helper`) remain flagged.

Owning-package detection:

- Single-package projects: every test belongs to the lone package.
- Multi-package projects: the owner is inferred from the test path under
  `tests/` (e.g. `tests/pkg_b/test_x.py` → `pkg_b`); tests not nested
  under a recognized package directory are treated as cross-package.

### Fix recipes

- Export the symbol: drop the `_` prefix and add it to the package
  `__all__` / `__init__.py`.
- Pull the helper into a test-only fixture or factory.
- Move the assertion one layer up so it exercises the public entry point.

## Pyramid v6

**Rule ID**: `TEST_QUALITY_PYRAMID_LEVEL`
**Class**: `axm_audit.core.rules.test_quality.pyramid_level.PyramidLevelRule`
**Severity**: `WARNING`
**Score**: `max(0, 100 - n_mismatches * 2)`

Classifies every `tests/**/test_*.py` function into `unit`, `integration`, or
`e2e` based on five soft-signal rules (R1–R5) and reports findings when the
classified level does not match the folder the test lives in.

### Scoping rules

| Rule | What it catches | Example signal |
| -- | -- | -- |
| **R1** — import-IO attribution | Module-level `import httpx` only counts as I/O when the function body references `httpx`. Cuts false positives from shared imports in pure-function tests. | `imports httpx` |
| **R2** — public-only rescue | Tests that import only public (`__all__`) symbols and do no I/O stay `unit`, even under `tests/integration/`. Fires **before** the generic `has_public → integration` branch. | reason `"public API import, no real I/O"` |
| **R3** — per-function attr-IO + guards | Attr-IO (`.write_text`, `.mkdir`, `open()`) is traced through helper calls up to depth 2; a **hard-writer-attr guardrail** keeps `mock-neutralized` from downgrading a test whose body genuinely writes. Also covers `tmp_path`-as-arg taint and fixture-arg tracking. | `attr:.write_text()`, `fixture-arg:tmp_path_factory`, `tmp_path-as-arg` |
| **R4** — conftest-aware fixtures | Fixtures defined in ancestor `conftest.py` files (walked up to `tests/` or the package root) are resolved and flagged when they perform real I/O. | `conftest-fixture-io:tmp_db` |
| **R5** — mock neutralization | When `@patch` / `mock.patch` targets an I/O symbol and no hard signal fires (`tmp_path+write/read`, writer `attr:`), the test's `has_real_io` flips back to `False`. Never applies under subprocess / CLI runner. | `mock-neutralized:module.open,module.write_text` |

The **hard-writer-attr guardrail** is explicit in R3: if the function body
contains a writer attribute call like `.write_text`, R5 cannot neutralize it,
even under `@patch("module.open")`. This prevents a misplaced patch decorator
from lying about real I/O.

Subprocess detection is narrowed to package-owned entry points, resolved by
`load_cli_binaries`: the union of the `[project.scripts]` keys and the generic
`axm` binary, the latter added only when the package declares a **non-empty**
`[project.entry-points."axm.tools"]` table (whose keys are tool names, never
binaries). An `axm.tools`-only package therefore resolves `{axm}`, so its
black-box `subprocess.run(["axm", <tool>, ...])` test classifies `e2e`. Runner
prefixes such as `uv run` are peeled until a resolved binary is found, and
`python -m <binary>` / `python -m <binary>.module` match the binary's
hyphen→underscore module alias. A package declaring neither table resolves no
binary at all and gets no `e2e` classification — plumbing commands such as
`git`, `pip`, `uv venv`, and `python -c` never force `e2e` on their own.

### Classification branches

| `has_real_io` | `has_subprocess` | `imports_public` | `imports_internal` | Level | Reason |
| -- | -- | -- | -- | -- | -- |
| * | True | * | * | `e2e` | subprocess / CLI runner invocation |
| False | False | True | False | `unit` | public API import, no real I/O (pure function) |
| True | False | * | * | `integration` | real I/O (with/without imports) |
| False | False | False | True | `unit` | internal import, no real I/O |
| False | False | False | False | `unit` | no real I/O, no package import |

## Duplicates

**Rule ID**: `TEST_QUALITY_DUPLICATE_TESTS`
**Class**: `axm_audit.core.rules.test_quality.DuplicateTestsRule`
**Severity**: `WARNING`
**Score**: `max(0, 100 - n_clustered_pairs * 5)`

Clusters likely-duplicate test functions across the `tests/**/test_*.py`
tree using structural **signals** and rescue **anti-signals**. A
"clustered pair" counts against the score only when no rescue fires;
ambiguous clusters are surfaced but do not dock points.

### Signals

| Signal | What it catches | AXM example |
| -- | -- | -- |
| **S1** — call + assert fingerprint | Same SUT call signature (`mod.func(2)`) and same normalized assert pattern across the tree. | `axm-ticket/tests/unit/test_parse_symbols.py::test_parses_single_symbol` vs `..._parses_two_symbols` — both reduced to `parse(STR) == LIST`; S1 clustered, P1 rescued them on distinct literals. |
| **S2** — cross-file same-name + high similarity + **shared SUT** | Tests with identical names across files whose statement-set Jaccard ≥ `0.95` **and which share at least one first-party SUT symbol**. The shared-SUT gate is required because the statement-set normalizes away symbol identity: two same-named tests of *different* rules/parsers that merely share an `assert result.passed` / `result.details` skeleton are **not** fused. | Two `test_handles_empty_input` — one in `test_parser.py`, one in `test_lexer.py` — with identical bodies *both calling `parse(...)`*; S2 flagged a real copy-paste. |
| **S3** — intra-file Jaccard ≥ threshold | Statement-set similarity ≥ `ast_similarity_threshold` (default `0.8`) within the same file. | `axm-mail/tests/test_format.py::test_format_plain` vs `test_format_html` — 0.92 Jaccard; S3 clustered, P2 rescued on different `@patch` targets. |

### Anti-signals (rescues)

| Rescue | Trigger | AXM example |
| -- | -- | -- |
| **P1** — distinct literals | Pair differs on ≥ 2 distinct str/bytes literals per side → `ambiguous_distinct_literals`. | Varying-input parametrize-like tests kept as separate behaviors. |
| **P2** — patch context | Pair exercises different `(decorator, with, mocker)` patch shapes → `ambiguous_patch_context`. | `test_retry_on_5xx` vs `test_retry_on_timeout` — same body shape, different `mocker.patch` targets. |
| **P3** — template pair | Cross-file pair with a ≥ 4-char token diff in filename stem and body ≤ 4 child nodes → `ambiguous_template_pair`. | Per-adapter smoke tests (`test_postgres.py` vs `test_sqlite.py`). |
| **P4** — body size | Intra-file pair whose largest body has ≤ 8 child nodes → `ambiguous_body_size`. | Trivially small smoke tests that look alike by accident. |
| **P8** — distinct parent class | Clustered tests live in ≥ 2 distinct enclosing test classes → `ambiguous_distinct_class`. | Per-scenario `TestX` / `TestY` classes sharing a method shape. |
| **P9** — pytest.raises divergence | Some clustered tests wrap their SUT call in `with pytest.raises(...)` while others do not → `ambiguous_raises_divergence`. | Happy-path vs error-path pairs over the same call signature. |

### Collection scope

The rule walks `tests/**/test_*.py` but **excludes `tests/fixtures/**` by
default** — fixture corpora (e.g. `tests/fixtures/fix_corpus/{input,expected}/`
snapshots fed to the fix-pipeline tests) are static data, near-identical by
construction, and are *not* the suite's own tests. They are skipped before
clustering, so they never produce false positives.

### Exemptions

Two complementary mechanisms suppress a known cluster:

| Mechanism | Survives refactors? | Use for |
| -- | -- | -- |
| `exempt_paths` globs | ✅ (path-based) | Whole test files / subtrees that should never be clustered. |
| `acknowledged` by-hash | ❌ (hash drifts on membership change) | A single validated residual cluster you want to keep flagged-but-accepted. |

`exempt_paths` uses the same glob semantics as `MirrorRule.exempt_paths`
(segment-wise `fnmatch`, a literal `**` segment spans path segments). Matched
files are dropped from collection — surviving renames within the glob:

```toml
[tool.axm-audit.duplicate_tests]
# Drop generated / contract test trees from dedup entirely.
exempt_paths = ["tests/integration/contracts/*.py", "tests/generated/**"]

# Accept one genuine same-SUT intra-file residual by its cluster hash.
[[tool.axm-audit.duplicate_tests.acknowledged]]
hash = "a1b2c3d4e5f6"
reason = "validated: distinct branches, parametrize would hurt"
```

A `hash` whose cluster no longer exists is reported under
`metadata["stale_acknowledged"]` and rendered as a `⚠ stale acknowledged
cluster` line — it never affects the score, so prefer `exempt_paths` for
anything structural.

## Tautology Triage v4

`TEST_QUALITY_TAUTOLOGY` detects shallow or tautological assertions, then
classifies findings into review actions. Its score is
`max(0, 100 - 2 * counted_findings)`; it passes only with no counted findings.
`KEEP` marker opt-outs remain in metadata but are not counted.

Read the [patterns, ordered triage ladder, markers and payload](reference/tautology.md).
A `DELETE` suggestion requires checking the scenario's actual coverage.

## No-Package-Symbol

**Rule ID**: `TEST_QUALITY_NO_PACKAGE_SYMBOL`
**Class**: `axm_audit.core.rules.test_quality.NoPackageSymbolRule`
**Severity**: `WARNING`
**Score**: `max(0, 100 - n_findings * 2)`

Flags `tests/integration/**` and `tests/e2e/**` test files that satisfy
**neither** criterion:

* **Criterion (a) — first-party symbol exercise.** The test (or any
  module-level helper it transitively calls, or any `pytest.fixture`
  whose return-type annotation or return/yield value resolves to a
  first-party alias) references a symbol imported from a package
  declared under `src/`.
* **Criterion (b) — in-package script invocation.** The closure invokes
  a declared `[project.scripts]` entrypoint via `subprocess.run`,
  `subprocess.call`, ``python -m <pkg>`` (after the script's hyphen→underscore
  alias), or `CliRunner().invoke(app, [...])` for single-script packages.

`tests/unit/**` is skipped — the rule does not apply at the unit tier.

### Verdicts

| Verdict | Triggered when | Fix |
| -- | -- | -- |
| `MISLOCATED_INTEGRATION` | only criterion (a) passes, and the file lives in `tests/e2e/` | Move the file to `tests/integration/` — it exercises Python symbols, not the package CLI. |
| `NO_PACKAGE_SYMBOL` | neither criterion passes | Express the invariant as a versioned rule of the target package, or move the check to a doc/packaging linter outside the pytest suite. |

A file is reported only when **every** unmarked test in the file fails
both criteria — a mix of one fixture-validation test plus one
symbol-exercising test is still OK.

### Marker opt-out

Use `pytest.mark.no_package_symbol_ok` to suppress the rule on a single
test or an entire file:

```python
import pytest

pytestmark = pytest.mark.no_package_symbol_ok  # file-wide

@pytest.mark.no_package_symbol_ok            # per-test
def test_distributable_artefact_packaging(): ...
```

The marker is appropriate when the test legitimately verifies a
non-package property (e.g. a packaging invariant, a packaging-linter
output) that the project deliberately encodes as pytest.

### Single source of truth

Binary resolution and the permissive argv reconstruction live in
`axm_audit.core.rules.test_quality._shared` (`load_project_scripts`,
`load_cli_binaries` / `cli_binaries_from_pyproject`,
`has_in_package_subprocess_invocation` and their private helpers). Both
`NoPackageSymbolRule` and `PyramidLevelRule` consume the same matcher — no
duplicate definitions — but they differ on the *resolver*: this rule reads the
strict `[project.scripts]` set via `load_project_scripts`, while
`PyramidLevelRule` uses the CLI-scoped `load_cli_binaries` (scripts ∪ `axm`
for `axm.tools` packages). The widened resolution stays confined to the
pyramid call site; `load_project_scripts` keeps its narrow contract for
`FileNamingRule` and the fix pipeline.

## File-Naming

**Rule ID**: `TEST_QUALITY_FILE_NAMING`
**Class**: `axm_audit.core.rules.test_quality.FileNamingRule`
**Severities**: `INFO` (NAME_MISMATCH), `WARNING` (SPLIT, COLLIDE)
**Score**: `max(0, 100 - 1 * n_info - 3 * n_warning)`

Derives a canonical `test_*.py` filename for every `tests/integration/**`
and `tests/e2e/**` file from the top-K=2 tuple of (first-party symbols
| `(bin, sub)` CLI invocations) and compares it with the current
basename. `tests/unit/**` is skipped — that naming convention is
enforced by `PRACTICE_TEST_MIRROR`.

### Canonical filename emission

| Tier | Input tuple | Emission |
| -- | -- | -- |
| `integration` | top-K=2 first-party symbols, alphabetical | `test_{s1}__{s2}.py` (snake_case, joined by `__`) |
| `integration` | top-K=1 | `test_{s1}.py` |
| `e2e` (multi-binary) | top-K=2 `(bin, sub)` | `test_{bin1}__{sub1}__{bin2}__{sub2}.py` |
| `e2e` (single-binary) | `(fixture-cli, "audit")` | `test_audit.py` (binary prefix stripped) |
| `e2e` (single-binary) | `(fixture-cli, "")` | `test_fixture_cli.py` (bare binary kept) |

Single-binary collapse is gated on `len([project.scripts]) == 1`. Multi-binary
CliRunner attribution falls back to "skip" when ambiguous.

### Verdicts

| Verdict | Severity | Triggered when | Payload fields |
| -- | -- | -- | -- |
| `NAME_MISMATCH` | INFO | the file's basename differs from its canonical emission | `current_name`, `proposed_name`, `tuple`, `tier` |
| `SPLIT` | WARNING | the file's tests resolve to ≥2 distinct canonical tuples | `tuples`, `suggested_splits`, `tier` |
| `COLLIDE` | WARNING | two or more files in the same tier emit the same canonical name | `canonical_name`, `files`, `tier` |

`NAME_MISMATCH` is INFO because, on packages with ≥70% cohesion, human
scenario names often communicate more than the canonical tuple — the
finding surfaces the divergence as signal, not as a defect. `SPLIT` and
`COLLIDE` are WARNING because they describe pathologies of the file
boundary, independent of name choice.

### Marker opt-out

Use `pytest.mark.scenario_name_ok` to declare that the current basename
is intentional. The marker suppresses both `NAME_MISMATCH` and `SPLIT`
(a named scenario is allowed to span several symbol tuples); `COLLIDE`
still applies, since two files resolving to one name is a cross-file
clash unrelated to whether either file is a named scenario:

```python
import pytest

pytestmark = pytest.mark.scenario_name_ok  # file-wide
```

### Shared helpers

`canonical_filename`, `first_party_symbol_counts`, and `cli_invocation_tuple`
live in `axm_audit.core.rules.test_quality._shared` (alongside the
`NoPackageSymbolRule` helpers). They consume the bare test body — no
helper closure — so the canonical tuple reflects direct usage frequency.

### Public helper: `compute_canonical_name`

`axm_audit.core.rules.test_quality.compute_canonical_name(test_file, project_path)`
returns the canonical `test_*.py` basename that `FileNamingRule` would emit
for a single integration / e2e test file, or `None` when the file is not
in an integration / e2e tier, has no test functions, or has no first-party
symbol coverage. Both the rule loop and the helper flow through a single
internal pipeline (`_verdict_for_file` → `_aggregate_file`) — there is no
parallel implementation of the top-K computation.

`AntiMirrorRule` (`PRACTICE_TEST_SCENARIO_NAMING`) consumes this helper to
suppress a false positive: when an integration test's stem equals the
canonical K=1 name FILE_NAMING would emit *and* the file's tests cover
exactly one distinct symbol tuple, the anti-mirror violation is dropped.
Renaming would re-fire `NAME_MISMATCH`, so the K=1 collision with a source
module basename is not actionable. Anti-mirror still fires on K≥2 mirrored
stems (where FILE_NAMING also emits `SPLIT`) and on genuine mis-names
(stem matches a source module but tests cover a different symbol).

## Validation and limits

These are static heuristics, not proofs of behavioral redundancy or absence
of I/O. Resolve findings against the test scenario before changing code.
Historical internal/external corpus measurements do not establish a current
false-positive rate or make every DELETE verdict safe to apply automatically.

The naming and no-package-symbol checks currently require the literal
`tests/` directory; a custom-only `tests_axm_*/` layout may skip those
checks. See [configuration and exclusions](reference/configuration.md).
