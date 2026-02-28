# CLI Reference

## Global Options

```
axm-init --help       Show help
axm-init --version    Show version
```

## `scaffold` — Scaffold a Project

```
axm-init scaffold [OPTIONS] [PATH]
```

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `PATH` | | string | `.` | Directory to initialize project in |
| `--name` | `-n` | string | *dir name* | Project name (defaults to directory name) |
| `--org` | `-o` | string | *required* | GitHub org or username |
| `--author` | `-a` | string | *required* | Author name |
| `--email` | `-e` | string | *required* | Author email |
| `--license` | `-l` | string | `Apache-2.0` | License type (MIT, Apache-2.0, EUPL-1.2) |
| `--license-holder` | | string | *--org* | License holder (defaults to --org) |
| `--description` | `-d` | string | `""` | Project description |
| `--check-pypi` | | bool | `False` | Check PyPI name availability first |
| `--json` | | bool | `False` | Output as JSON |

**Validation rules:**

- Missing `--name` → defaults to target directory name
- Missing `--org`, `--author`, or `--email` → exit code 1
- `--license-holder` omitted → defaults to `--org` value
- `--check-pypi` with taken name → exit code 1

**Example:**

```bash
axm-init scaffold my-project --name my-project \
  --org axm-protocols --author "Your Name" --email "you@example.com"
```

```
✅ Project 'my-project' created at /path/to/my-project
   📄 pyproject.toml
   📄 src/my_project/__init__.py
   📄 tests/__init__.py
```

---

## `reserve` — Reserve Package Name on PyPI

```
axm-init reserve [OPTIONS] NAME
```

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `NAME` | | string | *required* | Package name to reserve |
| `--author` | `-a` | string | `John Doe` | Author name |
| `--email` | `-e` | string | `john.doe@example.com` | Author email |
| `--dry-run` | | bool | `False` | Skip actual publish |
| `--json` | | bool | `False` | Output as JSON |

**Token resolution:**

1. `PYPI_API_TOKEN` environment variable
2. `~/.pypirc` `[pypi]` password field
3. Interactive prompt (if TTY)

**Example:**

```bash
axm-init reserve my-cool-package --dry-run
```

```
✅ Dry run — would reserve 'my-cool-package' on PyPI
   View at: https://pypi.org/project/my-cool-package/
```

---

## `check` — Check Project Against AXM Standard

```
axm-init check [OPTIONS] [PATH]
```

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `PATH` | | string | `.` | Directory to check |
| `--json` | | bool | `False` | Output as JSON |
| `--agent` | | bool | `False` | Compact agent-friendly output |
| `--category` | `-c` | string | *all* | Filter to one category |

**Available categories:** `pyproject`, `ci`, `tooling`, `docs`, `structure`, `deps`, `changelog`

**Exit codes:**

- `0` — Score is 100/100
- `1` — Score below 100 (failures found)

**Example:**

```bash
axm-init check
```

```
📋 AXM Check — my-project
   Path: /path/to/my-project

  pyproject (30/30)
    ✅ pyproject.exists                 5/5  pyproject.toml found
    ...

  Score: 97/100 — Grade A 🏆

  📝 Failures (1):

  ❌ docs.readme (3 pts)
     Problem: README missing 1 section(s)
     Missing: Development
     Fix:     Add Development section(s) to README.md.
```

**JSON output:**

```bash
axm-init check --json
```

```json
{
  "project": "/path/to/my-project",
  "score": 97,
  "grade": "A",
  "categories": { "pyproject": { "earned": 30, "total": 30 } },
  "failures": [
    { "name": "docs.readme", "weight": 3, "fix": "Add Development..." }
  ]
}
```

---

## `version` — Show Version

```
axm-init version
```

**Example:**

```bash
axm-init version
```

```
axm-init 0.1.0
```
