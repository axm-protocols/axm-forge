# CLI Reference

## Commands

`axm-audit` exposes five subcommands: `audit`, `fix`, `test`, `test-quality`,
and `version`.

### `axm-audit audit`

Audit a project's code quality against the AXM standard.

```
axm-audit audit [PATH] [--json] [--agent] [--category|-c CATEGORY]
```

| Flag | Default | Effect |
| -- | -- | -- |
| `PATH` | `.` | Project root to audit |
| `--json` | `false` | Output as JSON (`format_json`) |
| `--agent` | `false` | Compact agent-friendly output (`format_agent_text`) |
| `--category`, `-c` | *all* | Filter to one category (lint, type, security, complexity, architecture, test_quality, practices, deps, testing, structure, tooling) |

Exit code is `1` when `quality_score` falls below the `PASS_THRESHOLD` (90),
`0` otherwise.

### `axm-audit fix`

Deterministically reorganise a project's test suite. Dry-run by default — pass
`--apply` to mutate the project. If the baseline test suite is red it warns and
proceeds anyway (parity is the caller's responsibility).

```
axm-audit fix [PATH] [--apply] [--rules RULE_IDS]
```

| Flag | Default | Effect |
| -- | -- | -- |
| `PATH` | `.` | Project root to fix |
| `--apply` | `false` | Mutate the project (default: dry-run) |
| `--rules` | `TEST_QUALITY_PYRAMID_LEVEL,TEST_QUALITY_FILE_NAMING` | Comma-separated `rule_id`s to fix |

### `axm-audit test`

Run tests with structured output.

```
axm-audit test [PATH] [--files FILES] [-m|--markers MARKERS] [-x|--stop-on-first] [--agent]
```

| Flag | Default | Effect |
| -- | -- | -- |
| `PATH` | `.` | Project root to test |
| `--files` | *all* | Specific test files to run |
| `--markers`, `-m` | *none* | Pytest markers to filter |
| `--stop-on-first`, `-x` | `true` | Stop on first failure |
| `--agent` | `false` | Compact agent-friendly output (`format_audit_test_text`); without it, output is JSON |

Exit code is `1` when any test failed or errored, `0` otherwise.

### `axm-audit test-quality`

Audit test quality (pyramid, duplicates, tautologies, private imports).

```
axm-audit test-quality [PATH] [--json] [--mismatches-only] [--agent]
```

| Flag | Default | Effect |
| -- | -- | -- |
| `PATH` | `.` | Project root to analyse |
| `--json` | `false` | Emit the JSON superset (clusters + verdicts + pyramid + private imports) |
| `--mismatches-only` | `false` | Render only the pyramid section, filtered to folder↔level mismatches |
| `--agent` | `false` | Compact agent-friendly output (delegates to `format_agent_text`) |

Exit code is `1` when the aggregate `quality_score` falls below the
`PASS_THRESHOLD`, `0` otherwise. Sections are emitted in fixed order:
private imports → pyramid → duplicates → tautologies.

### `axm-audit version`

Print the installed `axm-audit` version.

```
axm-audit version
```

## Python API

Auto-generated API reference is available under [Python API](../../reference/axm_audit/index.md).

### Formatters

- `format_test_quality_text(result, mismatches_only=False) -> str` — render
  the four base test-quality sections (private imports, pyramid, duplicates,
  tautologies) as plain text, plus `NO_PACKAGE_SYMBOL` and `FILE_NAMING`
  sections when present. With `mismatches_only=True`
  only the pyramid section is emitted, filtered to entries whose folder
  differs from the classified level.
- `format_test_quality_json(result) -> dict` — JSON superset returning
  `{score, grade, rules, clusters, verdicts, pyramid_mismatches,
  private_import_violations, no_package_symbol, file_naming}` (`rules` is
  the sorted list of every `TEST_QUALITY_*` rule id that was evaluated).
