# Test Quality Rules

The `test_quality` category surfaces rules that reason about the **test tree
itself** — what it imports, how it asserts, which fixtures do real I/O. Unlike
`testing` (which just gates coverage), `test_quality` rules guard against
brittleness: tests that couple to implementation details, tautological
asserts, or mock patterns that drift from production behavior.

Rules land incrementally; this page documents each as it ships.

## private-imports

**Rule ID**: `TEST_QUALITY_PRIVATE_IMPORTS`
**Class**: `axm_audit.core.rules.test_quality.PrivateImportsRule`
**Severity**: `ERROR`
**Score**: `max(0, 100 - n_violations * 5)`

Flags `tests/**/test_*.py` imports of `_prefixed` symbols from first-party
packages. Importing private helpers couples the test suite to implementation
details, so a simple refactor of a private function turns into a multi-file
chore.

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

### Why it matters

- **Refactor friction** — renaming `_helper` should not break the test suite.
- **API honesty** — if a test needs `_private`, the symbol is probably part of
  the package's effective contract and should be exported (dropping the `_`)
  or replaced with a test-facing seam.
- **Review signal** — new private imports in tests often hide a missing
  abstraction.

### Configuration

```python
from axm_audit.core.rules.test_quality import PrivateImportsRule

# Also flag _UPPER_CASE constants (default: ignored)
rule = PrivateImportsRule(include_constants=True)
```

### Fix recipes

- Export the symbol: drop the `_` prefix and add it to the package
  `__all__` / `__init__.py`.
- Pull the helper into a test-only fixture or factory.
- Move the assertion one layer up so it exercises the public entry point.

## pyramid-level

**Rule ID**: `TEST_QUALITY_PYRAMID_LEVEL`
**Class**: `axm_audit.core.rules.test_quality.pyramid_level.PyramidLevelRule`
**Severity**: `WARNING`
**Score**: `max(0, 100 - n_mismatches * 2)`

Classifies every `tests/**/test_*.py` function into `unit`, `integration`, or
`e2e` based on soft signals (R1 + R2 + R3 of the pyramid scoping stack) and
reports findings when the classified level does not match the folder the test
lives in.

### Signal stack

| Rule | What it catches | Example signal |
| -- | -- | -- |
| **R1** — import attribution | Module-level `import httpx` only counts as I/O when the function body references `httpx` | `imports httpx` |
| **R2** — public-only rescue | Tests that import only public (`__all__`) symbols and do no I/O stay `unit`, even under `tests/integration/` | reason `"public API import, no real I/O"` |
| **R3** — per-function I/O | Attr-IO (`.write_text`, `.mkdir`, `open()`) traced through helpers up to depth 2; fixture-arg guard; `tmp_path`-as-arg taint | `attr:.write_text()`, `fixture-arg:tmp_path_factory`, `tmp_path-as-arg` |

Additional built-ins:

- **tmp_path boundary** — `tmp_path.write_text(...)` emits `tmp_path+write/read`
- **CLI runner** — `CliRunner().invoke(app)` or `runner.invoke(app)` flips
  `has_subprocess=True` and classifies as `e2e`
- **Mock-name skip** — fixture args starting with `mock_`/`fake_`/`stub_` or
  containing `mock`/`fake`/`stub` are not treated as I/O sources

### Classification — eight canonical branches

| `has_real_io` | `has_subprocess` | `imports_public` | `imports_internal` | Level | Reason |
| -- | -- | -- | -- | -- | -- |
| * | True | * | * | `e2e` | subprocess / CLI runner invocation |
| False | False | True | False | `unit` | public API import, no real I/O (pure function) |
| True | False | * | * | `integration` | real I/O (with/without imports) |
| False | False | False | True | `unit` | internal import, no real I/O |
| False | False | False | False | `unit` | no real I/O, no package import |

The R2 public-only rescue fires **before** the generic `has_public → integration`
branch, so pure-function tests under `tests/integration/` are classified
correctly as `unit`.

### Findings

Each finding exposes:

- `level` — classified pyramid level (`unit` / `integration` / `e2e`)
- `reason` — one of the eight canonical reasons
- `current_level` — folder-derived level (`unit` / `integration` / `e2e` / `root`)
- `has_real_io`, `has_subprocess` — boolean soft signals
- `io_signals` — ordered list of triggering signals
- `imports_public`, `imports_internal` — per-symbol import classification
- `suggested_file` — e.g. `unit/core/test_parser.py`

### Configuration

```python
from axm_audit.core.rules.test_quality.pyramid_level import PyramidLevelRule

# Default: report every folder↔level mismatch as a finding
rule = PyramidLevelRule(strict_mismatches=True)
```
