# Tautology triage

This page details the Python heuristic behind
[`TEST_QUALITY_TAUTOLOGY`](../test_quality.md#tautology-triage-v4).
Verdicts are review suggestions, not permission to delete tests.
Historical corpus example names illustrate rule shapes; they are not a list
of files guaranteed to exist in the current workspaces.

## Rule contract

**Rule ID**: `TEST_QUALITY_TAUTOLOGY`
**Class**: `axm_audit.core.rules.test_quality.tautology.TautologyRule`
**Severity**: `WARNING`
**Score**: `max(0, 100 - n_findings * 2)`

Detects test functions whose asserts can never fail, then triages each
finding into `DELETE` / `STRENGTHEN` / `UNKNOWN` by walking an ordered ladder over delete-side, precondition, and strengthen-side checks. The rule
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

### The triage ladder

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
| `step_n2_import_smoke` | DELETE | Body is `from X import Y; assert Y is not None`-shaped | `example/tests/test_imports.py::test_imports_ok` — redundant with `test_protocol_tools_init`. |
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
| `step_4d_mocked_sut_contract` | STRENGTHEN | Mocked SUT is invoked and the result is `isinstance`-checked | `example/tests/test_client.py::test_client_returns_dict`. |
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
rather than deleted.

### Finding shape

`metadata["verdicts"]` is a `list[dict]`; each entry exposes:

- `file` — path relative to the project root
- `test` — test function name
- `line` — line number of the triggering assert
- `pattern` — one of the six detection patterns above
- `rule` — triage step that fired (e.g. `step_0b_n_copies_constructor`)
- `verdict` — `DELETE` / `STRENGTHEN` / `UNKNOWN` / `KEEP` (`KEEP` set by the marker opt-out; counted toward `metadata["verdicts"]` but excluded from the rule's finding count)
- `reason` — human-readable explanation from the triage step
