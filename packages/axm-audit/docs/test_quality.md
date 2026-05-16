# Test Quality Rules

The `test_quality` category surfaces rules that reason about the **test tree
itself** — what it imports, how it asserts, which fixtures do real I/O. Unlike
`testing` (which just gates coverage), `test_quality` rules guard against
brittleness: tests that couple to implementation details, tautological
asserts, or mock patterns that drift from production behavior.

## CLI

```
axm-audit test-quality [PATH] [--json] [--mismatches-only] [--agent]
```

Runs the `test_quality` category and prints the five sections (private
imports → pyramid → duplicates → tautologies → no-package-symbol). Use
`--json` for the machine-readable superset (`format_test_quality_json`,
which also exposes a sorted `rules` array of every `TEST_QUALITY_*` rule
id that was evaluated), `--agent` for the compact agent renderer, or
`--mismatches-only` to focus on pyramid folder↔level violations. Exits
`1` when the aggregate score falls below `PASS_THRESHOLD`. See the
[CLI reference](reference/cli.md) for details.

## Private Imports

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
| **DELETE** | The test asserts a private helper directly; the scenario is already covered by a public-API test. Drop the redundant test. | `axm-engine/tests/unit/test_hooks_internal.py::test__normalize_params` — removed after `test_hook_run.py` covered the same path via the public `Hook.run()` entry point. |
| **REFACTOR** | The test is valuable but reaches through a private surface. Replace the private symbol with a fixture, factory, or public seam. | `axm-audit/tests/unit/core/test_coupling_scoring.py` stopped importing `_compute_fan_out` and now drives scoring via a `CouplingMetricRule` instance. |
| **PROMOTE** | The private helper is de-facto public; the right fix is to drop the `_` prefix and export it. | `axm-nexus/tests/test_registry.py` triggered promoting `_ResourceCatalog._load` to `ResourceCatalog.load` plus an `__all__` entry. |

### What it flags

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

Subprocess detection is narrowed to package-owned entry points when the package
declares `[project.scripts]`: runner prefixes such as `uv run` are peeled until
a declared script is found, and `python -m package.module` matches the module
alias derived from that script name. Plumbing commands such as `git`, `pip`,
`uv venv`, and `python -c` do not force `e2e` classification on their own.

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
tree using three structural **signals** and four rescue **anti-signals**. A
"clustered pair" counts against the score only when no rescue fires;
ambiguous clusters are surfaced but do not dock points.

### Signals

| Signal | What it catches | AXM example |
| -- | -- | -- |
| **S1** — call + assert fingerprint | Same SUT call signature (`mod.func(2)`) and same normalized assert pattern across the tree. | `axm-ticket/tests/unit/test_parse_symbols.py::test_parses_single_symbol` vs `..._parses_two_symbols` — both reduced to `parse(STR) == LIST`; S1 clustered, P1 rescued them on distinct literals. |
| **S2** — cross-file same-name + high similarity | Tests with identical names across files whose statement-set Jaccard ≥ `0.95`. | Two `test_handles_empty_input` — one in `test_parser.py`, one in `test_lexer.py` — with identical bodies; S2 flagged a real copy-paste. |
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

## Tautology Triage v4

**Rule ID**: `TEST_QUALITY_TAUTOLOGY`
**Class**: `axm_audit.core.rules.test_quality.tautology.TautologyRule`
**Severity**: `WARNING`
**Score**: `max(0, 100 - n_findings * 2)`

Detects test functions whose asserts can never fail, then triages each
finding into `DELETE` / `STRENGTHEN` / `UNKNOWN` by walking a fixed 22-step
order over delete-side, precondition, and strengthen-side checks. The rule
emits one entry per finding in `metadata["verdicts"]`; no source rewriting
happens here — downstream tooling consumes the verdicts.

### Detection patterns

| Pattern | Example | Trigger |
| -- | -- | -- |
| `trivially_true` | `assert True`, `assert [1]` | Constant truthy / non-empty literal |
| `self_compare` | `assert x == x`, `assertEqual(x, x)` | Both sides AST-equal |
| `isinstance_only` | `assert isinstance(r, dict)` | All asserts are shallow `isinstance` |
| `none_check_only` | `assert x is not None` | All asserts are not-None |
| `len_tautology` | `assert len(r) >= 0` | Length comparison always true |
| `mock_echo` | `mock.f.return_value = 1; assert f() == 1` | Asserts the value just stubbed |

### The 22-step triage ladder

Steps fire in order; the first matching step wins. The ladder has three
bands: **delete-side** (N-prefixed precondition checks that force
`DELETE`), **precondition** (structural rescues that short-circuit before
the strengthen ladder), and **strengthen-side** (uniqueness / edge-case
signals that keep the test).

#### Marker opt-out (highest priority)

`@pytest.mark.tautology_ok` (per-test) or `pytestmark = pytest.mark.tautology_ok` (file-level) lets authors explicitly mark an assertion as an intentional tautology. The marker fires **first** in the early-exit ladder, so it overrides every other step including the delete-side ones.

| Step | Verdict | Fires when | AXM example |
| -- | -- | -- | -- |
| `step0_marker_opt_out` | KEEP | Test or its enclosing module carries `pytest.mark.tautology_ok` | `axm-word/tests/unit/test_layout.py::test_default_pt_size_is_safe` — narrows a `float` to satisfy mypy before a typed call. |

The marker accepts an optional positional reason string (`@pytest.mark.tautology_ok("mypy narrow before typed call")`) which is captured into the verdict's `reason` field. Bare markers fall back to `"intentional tautology (no reason given)"`.

`KEEP` verdicts remain in `metadata["verdicts"]` for JSON consumers and audit trails but are excluded from the finding count (`_NON_TAUTOLOGY_ACTIONS`) and from the text rendering.

Downstream consumers using `--strict-markers` should register the marker in their own `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "tautology_ok: opt out of TEST_QUALITY_TAUTOLOGY (optional reason arg)",
]
```

#### Delete-side preconditions

| Step | Verdict | Fires when | AXM example |
| -- | -- | -- | -- |
| `step_n2_import_smoke` | DELETE | Body is `from X import Y; assert Y is not None`-shaped | `axm-engine/tests/services/tools/test_protocol_tools.py::test_imports_ok` — redundant with `test_protocol_tools_init`. |
| `step_n2b_lazy_import_sut` | STRENGTHEN | Same shape, but test sits in a `test_init.py` lazy-import surface | `axm-nexus/tests/test_package_init.py::test_lazy_imports` — kept: guards boot ordering. |
| `step_n2c_toplevel_import_not_none` | DELETE | `assert X is not None` where X is top-level-imported AND used by ≥ 1 sibling | `axm-audit/tests/unit/core/test_rules_loaded.py::test_rule_loaded` — sibling already exercises the rule. |
| `step_n1_no_siblings` | STRENGTHEN | File has a single test — nothing to dedupe against | `axm-commons/tests/test_retry.py::test_retry_once` — sole test, kept. |

#### Precondition rescues

| Step | Verdict | Fires when | AXM example |
| -- | -- | -- | -- |
| `step_0_self_compare` | STRENGTHEN | `self_compare` pattern — always rescued (author signals intent) | `axm-market/tests/test_ohlc.py::test_bar_equals_itself` — contract conformance. |
| `step_0c_contract_conformance` | STRENGTHEN | `isinstance(x, T)` where T is a local Protocol / stdlib ABC | `axm-portfolio/tests/test_positions.py::test_position_is_mapping`. |

#### Strengthen-side uniqueness signals

| Step | Verdict | Fires when | AXM example |
| -- | -- | -- | -- |
| `step_1a_unique_fn` | STRENGTHEN | SUT is not exercised by any sibling | `axm-sentiment/tests/test_lexicon.py::test_load_lexicon`. |
| `step_2_unique_io` | STRENGTHEN | Uses `tmp_path`/filesystem I/O not exercised by any sibling | `axm-bib/tests/integration/test_pdf_extract.py::test_extract_from_real_pdf`. |
| `step_3_unique_parametrize` | STRENGTHEN | Carries `@parametrize` while no sibling does | `axm-screener/tests/test_filters.py::test_filter_matrix`. |
| `step_4_boundary_literal` | STRENGTHEN | Exercises a boundary literal (`0`, `-1`, `""`, `b""`) unseen in siblings | `axm-backtest/tests/test_pnl.py::test_pnl_on_zero_volume`. |
| `step_4c_significant_setup` | STRENGTHEN | ≥ 4 non-trivial setup statements combined with a weak assert | `axm-broker/tests/test_router.py::test_complex_routing_setup`. |
| `step_1b_different_args` | STRENGTHEN | Same SUT, different literal args — runs before `step_0b` to rescue varying-args cases | `axm-ast/tests/test_parser.py::test_parses_single_line` vs `test_parses_multiline`. |
| `step_4b_name_edge` | STRENGTHEN | Name mentions an edge-case keyword (`empty`, `null`, `overflow`, …) | `axm-mail/tests/test_threading.py::test_handles_empty_thread`. |
| `step_4f_intentional_weakness` | STRENGTHEN | Docstring/comment explicitly flags a deliberately weak assertion | `axm-smelt/tests/test_rewrite.py::test_smoke_pass`. |
| `step_4d_mocked_sut_contract` | STRENGTHEN | Mocked SUT is invoked and the result is `isinstance`-checked | `axm-n8n/tests/test_client.py::test_client_returns_dict`. |
| `step_4e_homogeneity_check` | STRENGTHEN | `isinstance()` runs inside a loop / `all()` / `any()` — homogeneity contract | `axm-office/tests/test_docx.py::test_all_paragraphs_are_runs`. |

#### Delete-side constructor checks (after strengthen rescues)

| Step | Verdict | Fires when | AXM example |
| -- | -- | -- | -- |
| `step_0b_n_copies_constructor` | DELETE | Pure constructor + weak assert with ≥ 1 identical-args sibling | `axm-word/tests/test_doc.py::test_new_doc` duplicated by `test_new_empty_doc`. |
| `step_0b2_impure_sibling_covers_ctor` | DELETE | Pure-ctor test whose constructor is already exercised by an impure sibling | `axm-anvil/tests/test_forge.py::test_forge_init`. |
| `step_5_default_unknown` | UNKNOWN | Terminator — no step matched | `axm-formal/tests/test_proof.py::test_trivially_true` — left for human review. |

The step order is load-bearing: strengthen-side rescues (`step_2`–`step_4e`)
fire before the delete-side constructor checks (`step_0b` / `step_0b2`) so
that a weak constructor test carrying real edge-case signal is kept
rather than deleted. Note: the triage code itself uses the names without
the second underscore (e.g. `step0b_n_copies_constructor`); the `step_`
forms above are the documentation convention for this page.

### Finding shape

`metadata["verdicts"]` is a `list[dict]`; each entry exposes:

- `file` — path relative to the project root
- `test` — test function name
- `line` — line number of the triggering assert
- `pattern` — one of the six detection patterns above
- `rule` — triage step that fired (e.g. `step_0b_n_copies_constructor`)
- `verdict` — `DELETE` / `STRENGTHEN` / `UNKNOWN` / `KEEP` (`KEEP` set by the marker opt-out; counted toward `metadata["verdicts"]` but excluded from the rule's finding count)
- `reason` — human-readable explanation from the triage step

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

`[project.scripts]` resolution and the permissive argv reconstruction
live in `axm_audit.core.rules.test_quality._shared`
(`load_project_scripts`, `has_in_package_subprocess_invocation` and
their private helpers). Both `NoPackageSymbolRule` and `PyramidLevelRule`
consume them — no duplicate definitions.

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
| `integration` | top-K=2 first-party symbols, alphabetical | `test_{s1}-{s2}.py` (snake_case, dash-joined) |
| `integration` | top-K=1 | `test_{s1}.py` |
| `e2e` (multi-binary) | top-K=2 `(bin, sub)` | `test_{bin1}-{sub1}-{bin2}-{sub2}.py` |
| `e2e` (single-binary) | `(axm-audit, "audit")` | `test_audit.py` (binary prefix stripped) |
| `e2e` (single-binary) | `(axm-audit, "")` | `test_axm_audit.py` (bare binary kept) |

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
is intentional. The marker suppresses `NAME_MISMATCH` **only**; `SPLIT`
and `COLLIDE` still apply:

```python
import pytest

pytestmark = pytest.mark.scenario_name_ok  # file-wide
```

### Baseline snapshot

Running the rule on `axm-audit` itself produces a non-zero, stable set of
findings — the documented historical drift. A normalized snapshot lives
at `tests/unit/core/rules/test_quality/_baselines/axm_audit_file_naming.json`
and the integration test
`tests/integration/test_file_naming_baseline_on_axm_audit.py` asserts
parity with the live rule output. Regenerate the baseline only when an
intentional drift is part of the work in flight.

### Shared helpers

`canonical_filename`, `first_party_symbol_counts`, and `cli_invocation_tuple`
live in `axm_audit.core.rules.test_quality._shared` (alongside the
`NoPackageSymbolRule` helpers). They consume the bare test body — no
helper closure — so the canonical tuple reflects direct usage frequency.

## Validation

The v6 / v4 stacks were validated against the internal AXM corpus and an
external open-source corpus. Results:

| Corpus | Findings | DELETE verdicts | False positives |
| -- | -- | -- | -- |
| AXM internal (`axm-workspaces/**`) | 169 | 17 | 0 |
| External corpus | 126 | — | 1 |

Key numbers: **169** total findings on the internal corpus, **17** DELETE
verdicts confirmed by manual review with **0** false positives; **126**
findings on the external corpus with exactly **1** false positive flagged
during triage (`step_0b_n_copies_constructor` on a factory-style
constructor test). The delete-side ladder is therefore safe to apply
automatically on AXM packages; external application should keep the
`DELETE` verdict gated behind a human-in-the-loop review.
