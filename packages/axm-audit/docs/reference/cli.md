# CLI Reference

## Commands

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

## Python API

Auto-generated API reference is available under [Python API](../../reference/axm_audit/index.md).

### Formatters

- `format_test_quality_text(result, mismatches_only=False) -> str` — render
  the four test-quality sections as plain text. With `mismatches_only=True`
  only the pyramid section is emitted, filtered to entries whose folder
  differs from the classified level.
- `format_test_quality_json(result) -> dict` — JSON superset returning
  `{score, grade, clusters, verdicts, pyramid_mismatches, private_import_violations}`.
