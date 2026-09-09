# Scaffold command reference

[CLI index](cli.md)

## `init_scaffold` — Scaffold a Project

```
axm init_scaffold [OPTIONS] [PATH]
```

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `PATH` | | string | `.` | Directory to initialize project in |
| `--name` | | string | *dir name* | Project name (defaults to directory name) |
| `--org` | | string | *required* | GitHub org or username |
| `--author` | | string | *required* | Author name |
| `--email` | | string | *required* | Author email |
| `--license` | | string | `Apache-2.0` | License type (MIT, Apache-2.0, EUPL-1.2) |
| `--license-holder` | | string | *--org* | License holder (defaults to --org) |
| `--description` | | string | `""` | Project description |
| `--workspace` | | bool | `False` | Scaffold a UV workspace instead of a standalone package |
| `--member` | | string | `None` | Scaffold a member sub-package with this name |
| `--kind` | | string | `None` | Scaffold kind: `standalone`, `workspace`, `member`, `paper`, `experiment`, `protocol_unit`, `protocol` |
| `--framework` | | string | `python` | `python`, `node`, `svelte`; non-Python templates support standalone only |
| `--profile` | | string | `None` | `protocols` profile for Python |
| `--domain` | | string | `None` | Required with protocol profile |
| `--unit` | | string | `None` | Shared unit for protocol declarations |
| `--protocols` | | JSON list | `None` | Action-only protocol payloads |
| `--preview` | | bool | `False` | Plan protocol declarations without applying them |
| `--check-pypi` | | bool | `False` | Check PyPI name availability first |
| `--json-output` | | bool | `False` | Output as JSON |

**Validation rules:**

- Missing `--name` → defaults to target directory name
- Missing `--org`, `--author`, or `--email` → exit code 1
- `--license-holder` omitted → defaults to `--org` value
- `--workspace` and `--member` are mutually exclusive → exit code 1
- `--check-pypi` with taken name → exit code 1
- `--member` outside a workspace → exit code 1
- `--kind` outside the declared set (`standalone`, `workspace`, `member`,
  `paper`, `experiment`, `protocol_unit`, `protocol`) → exit code 1
- `--kind experiment` on a directory that is not a detected paper → exit code 1,
  and nothing is written under that directory

**Exit codes:**

- `0` — scaffold succeeded
- `1` — scaffold failed (validation, copier error, taken name, …)

The exit code is authoritative in **both** text and `--json-output` mode: a failure
always exits `1`, and the JSON payload carries the error or structured result
field describing the cause. Scripts may route on `$?`.

**Example:**

```bash
axm init_scaffold my-project --name my-project \
  --org axm-protocols --author "Your Name" --email "you@example.com"
```

```text
init_scaffold | ✓ | my-project (standalone) | <count> files
. : pyproject.toml ...
src/ : my_project/__init__.py ...
tests/ : __init__.py ...
```

This is an abbreviated output shape; the real count and file list depend on the template.

**Workspace example:**

```bash
axm init_scaffold --workspace --name my-workspace \
  --org axm-protocols --author "Your Name" --email "you@example.com"
```

**Member example** (run from inside a workspace):

```bash
axm init_scaffold --member my-lib \
  --org axm-protocols --author "Your Name" --email "you@example.com"
```

```text
init_scaffold | ✓ | my-lib (member) | <count> files
path: /path/to/workspace/packages/my-lib
patched root: <files actually changed>
```

Member data also contains `skipped_root_files` and `failed_root_files`. The
tool can return success after creating the member while some root patches failed;
inspect those fields before treating workspace integration as complete.

**Paper example** (`--kind paper`, into an empty directory):

```bash
axm init_scaffold my-paper --kind paper \
  --org axm-protocols --author "Your Name" --email "you@example.com" \
  --description "Attention study"
```

Renders `PLAN.md`, `PIPELINE.md` (the data-provenance skeleton), `README.md`,
`paper/` (LaTeX source + bibliography) and the `experiments/` root the tool
owns. `--description` becomes the paper title;
`--name` (or the directory name) is slugified into the paper slug.

**Experiment example** (`--kind experiment`, run against a scaffolded paper):

```bash
axm init_scaffold my-paper --kind experiment --name baseline \
  --org axm-protocols --author "Your Name" --email "you@example.com"
```

The experiment directory is named by the CLI, never by the template: the next
free zero-padded index followed by the slug (`experiments/01-baseline/`, then
`experiments/02-…`). Its `manifest.yaml` — the 1.1.0 experiment contract, keyed
`contract_version` / `id` / `title` / `question` / `type` / `repro_level`, plus
the optional `supports` list (the identifiers of the investigations the
experiment serves, rendered as an empty list) — is created at scaffold time,
before any script runs, and appears in the `files` list under `--json-output`.

Every entry of that `files` list is named relative to the payload's own `path`
(the experiment directory the scaffold produced), so joining `path` with an
entry always resolves on disk — `manifest.yaml`, `inputs/SOURCES.md`, … The
`paper` kind follows the same rule against the paper root it reports.


## Protocol and framework contracts

See [protocol declarations](protocol-scaffold.md) for preview and application,
and [template selection](templates.md) for the supported framework/type matrix.
`--preview` is a protocol-planning option, not a dry-run switch for every
scaffold mode. A protocol declaration request needs an existing package
`pyproject.toml`.

The standalone JSON payload contains `project_name`, `template` and `files`;
member, paper/experiment and protocol paths have their own additional fields.
Do not require a `path` field on every scaffold result. Early validation
errors in JSON mode use an `error` field.
