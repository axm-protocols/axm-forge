# CLI Reference

## Global Options

```
axm-init --help       Show help
axm-init --version    Show version
```

## `init` — Initialize a Project

```
axm-init init [OPTIONS] [PATH]
```

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `PATH` | | string | `.` | Directory to initialize project in |
| `--name` | `-n` | string | *dir name* | Project name (defaults to directory name) |
| `--template` | `-t` | string | `minimal` | Template: `python`, `minimal` |
| `--description` | `-d` | string | `""` | Project description |
| `--check-pypi` | | bool | `False` | Check PyPI name availability first |
| `--json` | | bool | `False` | Output as JSON |

**Validation rules:**

- Missing `--name` → defaults to target directory name
- Unknown `--template` → error with list of available templates
- `--check-pypi` with taken name → exit code 1

**Example:**

```bash
axm-init init my-project --name my-project --template minimal
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
| `--author` | `-a` | string | `Gabriel Jarry` | Author name |
| `--email` | `-e` | string | `jarry.gabriel@gmail.com` | Author email |
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
