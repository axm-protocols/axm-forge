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
| `--workspace` | `-w` | bool | `False` | Scaffold a UV workspace instead of a standalone package |
| `--member` | `-m` | string | `None` | Scaffold a member sub-package with this name |
| `--check-pypi` | | bool | `False` | Check PyPI name availability first |
| `--json` | | bool | `False` | Output as JSON |

**Validation rules:**

- Missing `--name` → defaults to target directory name
- Missing `--org`, `--author`, or `--email` → exit code 1
- `--license-holder` omitted → defaults to `--org` value
- `--workspace` and `--member` are mutually exclusive → exit code 1
- `--check-pypi` with taken name → exit code 1
- `--member` outside a workspace → exit code 1

**Exit codes:**

- `0` — scaffold succeeded
- `1` — scaffold failed (validation, copier error, taken name, …)

The exit code is authoritative in **both** text and `--json` mode: a failure
always exits `1`, and the `--json` payload carries `success` plus a `message`
field describing the cause. Scripts may route on `$?`.

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

**Workspace example:**

```bash
axm-init scaffold --workspace --name my-workspace \\
  --org axm-protocols --author "Your Name" --email "you@example.com"
```

**Member example** (run from inside a workspace):

```bash
axm-init scaffold --member my-lib \\
  --org axm-protocols --author "Your Name" --email "you@example.com"
```

```
✅ Member 'my-lib' created at /path/to/workspace/packages/my-lib
   📄 pyproject.toml
   📄 src/my_lib/__init__.py
   🔧 Patched root files: Makefile, mkdocs.yml, pyproject.toml
```

---

## `reserve` — Reserve Package Name on PyPI

```
axm-init reserve [OPTIONS] NAME
```

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `NAME` | | string | *required* | Package name to reserve |
| `--author` | `-a` | string | *git config* | Author name |
| `--email` | `-e` | string | *git config* | Author email |
| `--dry-run` | | bool | `False` | Skip actual publish |
| `--json` | | bool | `False` | Output as JSON |

**Default resolution for `--author` / `--email`:**
If omitted, resolved from `git config user.name` / `git config user.email`.
If git config is not available and neither flag is provided, `axm-init` exits with
code 1 and a descriptive error message (text or JSON depending on `--json`).

**Validation rules:**

- Empty `--author` or `--email` after git config fallback → exit code 1
- Placeholder values (`John Doe`, `john.doe@example.com`) are rejected by the MCP tool layer

**Token resolution:**

1. `PYPI_API_TOKEN` environment variable
2. `~/.pypirc` `[pypi]` password field
3. Interactive prompt (if TTY)

**Exit codes:**

- `0` — reservation succeeded (or dry-run completed)
- `1` — reservation failed (missing identity/token, name taken, …)

As with `scaffold`, the exit code is authoritative in both text and `--json`
mode — a failed reservation exits `1` and the JSON payload carries `success`
and `message`.

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
| `--verbose` | `-v` | bool | `False` | Show all checks including passed |
| `--category` | `-c` | string | *all* | Filter to one category |

**Available categories:** `pyproject`, `ci`, `tooling`, `docs`, `structure`, `deps`, `changelog`, `workspace`

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
axm-init check
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
axm-init check --json
```

```json
{
  "project": "/path/to/my-project",
  "score": 97,
  "grade": "A",
  "categories": { "pyproject": { "earned": 27, "total": 27 } },
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
