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
| `--kind` | | string | `None` | Scaffold kind: `standalone`, `workspace`, `member`, `paper`, `experiment`, `learning`, `protocol_unit`, `protocol` |
| `--framework` | | string | `python` | `python`, `node`, `svelte`; non-Python templates support standalone only |
| `--profile` | | string | `None` | `protocols` profile for Python |
| `--domain` | | string | `None` | Learning domain for `--kind learning`, or required protocol domain with `--profile protocols` |
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
  `paper`, `experiment`, `learning`, `protocol_unit`, `protocol`) → exit code 1
- `--kind experiment` → exit code 1 with guidance to use axm-lab
  `experiment_scaffold`; nothing is written
- Learning operations require `axm-learning[scaffold]`; no bundled fallback exists
- A learning re-run whose declared domain matches `--domain` reconciles either a
  standalone project or workspace member and preserves the recipe byte for byte
- A learning re-run with a different `--domain` → exit code 1 before rendering;
  the error names both domains and leaves training configuration and recipe bytes
  unchanged

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

**Papers:** install axm-lab and use `paper_scaffold` with workspace, venue,
year and slug. Init no longer bundles a paper template; `--kind paper`
returns an explicit routing error.

**Experiments:** install axm-lab and use its `investigation_scaffold` and
`experiment_scaffold` tools. The latter requires an owning investigation and
its active plan entry. Forge does not create flat paper experiments or legacy
1.x manifests.

## Learning example

```bash
axm init_scaffold learning-lab --kind learning --domain forecasting \
  --org axm-protocols --author "Your Name" --email "you@example.com"
```

For a standalone destination, the learning kind composes the ordinary Python
project as a base with the installed Learning provider’s `learning-project` overlay. It therefore
keeps the base repository tooling (`Makefile`, MkDocs, pre-commit and
`.github/`) and adds `training.toml`, `study.toml`,
`src/learning_lab/learning/recipe.py`,
`src/learning_lab/learning/tool.py` and
`tests_learning_lab/unit/test_recipe.py`. The generated training module reads
`training.toml`, performs a bounded deterministic local run and exposes both a
structured `TrainingTool` result and a module entry point that prints
`FINAL_LOSS=<value>`.

The structured scaffold result adds `profile="learning"`, `mode`,
`distribution` and `root` to the ordinary fields. The composed
`pyproject.toml` retains the base tooling tables, declares
`[tool.axm-init.learning]`, and registers
`learning_lab.learning.tool:TrainingTool` under `axm.tools`. Without
`--domain`, the domain defaults to the generated module name.

For a workspace member, add `--member learning-lab` and run against the
workspace. Members keep the single standalone learning layer because repository
tooling belongs to the workspace root. Re-running either form with the same
domain reconciles the existing learning scaffold: template-owned configuration
and base tooling are refreshed while the recipe is preserved byte for byte. A
different requested domain fails before rendering, with both the declared and
requested domains in the error.

## Protocol and framework contracts

See [protocol declarations](protocol-scaffold.md) for preview and application,
and [template selection](templates.md) for the supported framework/type matrix.
`--preview` is a protocol-planning option, not a dry-run switch for every
scaffold mode. A protocol declaration request needs an existing package
`pyproject.toml`.

The standalone JSON payload contains `project_name`, `template` and `files`;
member, paper and protocol paths have their own additional fields.
Do not require a `path` field on every scaffold result. Early validation
errors in JSON mode use an `error` field.

## Installed scaffold providers

`axm_init.scaffolding.render_scaffold(kind, destination, data, *, framework,
member=False)` creates projects only in missing or empty directories. Installed
`axm.scaffold_providers` entry points supply a zero-argument factory whose object
implements `layers(request)`. Layers-only providers remain supported.

`ScaffoldRequest(kind, framework=Framework.PYTHON, member=False, existing=False)`
selects the layout. `existing=True` is reserved for explicit overlay routes such
as the Learning tool, allowing providers to omit base templates that would
replace authored project configuration. The public create renderer always uses
`existing=False` and rejects existing content before invoking a provider.

Providers may implement `finalize(request, destination, data) -> None` to complete
domain metadata after all layers render successfully. The public renderer calls
this hook under its reentrant destination lock, with the original caller answers;
providers must resolve any omitted answer defaults themselves. Finalization must
preserve authored configuration when used by an overlay route. Exceptions produce
a failed scaffold result. Rendering and finalization are not transactional and
may leave partial output; a failed render never invokes finalization.
