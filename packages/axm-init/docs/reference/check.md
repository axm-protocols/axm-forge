# Check command reference

[CLI index](cli.md)

## `init_check` — Check Project Against AXM Standard

```
axm init_check [OPTIONS] [PATH]
```

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `PATH` | | string | `.` | Directory to check |
| `--json-output` | | bool | `False` | Output as JSON |
| `--agent` | | bool | `False` | Compact agent-friendly output |
| `--verbose` | | bool | `False` | Show all checks including passed |
| `--category` | | string | *all* | Filter to one category |

**Python categories:** `pyproject`, `ci`, `tooling`, `docs`, `structure`, `deps`,
`changelog`, `workspace`, `paper`, `experiment`. The selected framework can change
this registry; see [check catalogue](checks/catalogue.md).

**Exit codes:**

- `0` — Score is 100/100, or no weighted checks apply (N/A)
- `1` — Applicable score below 100, or an operational error

**Example:**

```bash
axm init_check --verbose
```

```
📋 AXM Check — my-project
   Path: /path/to/my-project

  pyproject (29/29)
    ✅ pyproject.pyproject_exists        4/4  pyproject.toml found
    ...

  Score: 97/100 — Grade A 🏆

  📝 Failures (1):

  ❌ docs.readme (3 pts)
     Problem: README missing 1 section(s)
     Missing: Development
     Fix:     Add Development section(s) to README.md.
```

**Check output with workspace context:**

```bash
axm init_check
```

```
📋 AXM Check — my-workspace
   Path: /path/to/my-workspace
   Context: WORKSPACE

  pyproject (29/29)
    ✅ pyproject.pyproject_exists        4/4  pyproject.toml found
    ...

  Score: 100/100 — Grade A 🏆
```

**JSON output:**

```bash
axm init_check --json-output
```

```json
{
  "score": 97,
  "grade": "A",
  "context": "standalone",
  "workspace_root": null,
  "excluded_checks": [],
  "passed_count": 40,
  "failures": [
    {
      "name": "docs.readme",
      "message": "README missing 1 section(s)",
      "details": ["Development"],
      "fix": "Add Development section(s) to README.md."
    }
  ]
}
```


## Output contract

The JSON example illustrates the schema; its score and counts are not a
measurement of your project. `--agent` and `--json-output` both select the
compact structured data shown above. The default is compact text, while
`--verbose` selects the expanded human report. JSON/agent takes precedence
over verbose.

A not-applicable run has `score: null` and `grade: null`; default text shows
`N/A`. This is distinct from an applicable zero score. Treat N/A explicitly
in CI rather than comparing null with a number. The tool writes a local quality
snapshot as part of a check run.

Operational errors may have no structured score payload and still appear on
stderr with a nonzero exit. The CLI does not expose an `--framework` override;
framework detection happens from the target files.
