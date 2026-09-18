# Template selection

`get_template_path(template_type, framework)` selects a bundled directory
by an exact pair. Unsupported combinations raise `KeyError`; there is no
fallback.

| Framework | Template type | Directory |
|---|---|---|
| python | standalone | python-project |
| python | workspace | uv-workspace |
| python | member | workspace-member |
| python | paper | paper-submodule |
| python | experiment | experiment |
| python | learning | learning-project |
| node | standalone | node-project |
| svelte | standalone | svelte-project |

The `protocols` profile adds metadata and declaration planning/application to
Python packages; it is not another framework template.

## Learning project and compatibility overlay

`TemplateType.LEARNING` with `Framework.PYTHON` selects `learning-project`.
The template has two explicit modes over the same learning contract.

The public `init_scaffold --kind learning` route selects `standalone` when no
member is supplied. It renders `pyproject.toml`, `README.md`, `training.toml`,
`study.toml`, the deterministic `src/<module_name>/recipe.py`, the AXMTool at
`src/<module_name>/tools/train.py`, and its seed unit test. Generated metadata
contains `[tool.axm-init.learning]` with a non-empty `domain`, plus an
`axm.tools` entry point targeting `<module_name>.tools.train:TrainingTool`.
The result reports `template="learning"`, `profile="learning"` and
`mode="standalone"`.

With `--member <name>` inside a UV workspace, the same template renders the
complete learning package under `packages/<name>/`. The result instead reports
`profile="learning"`, `mode="member"`, `distribution=<name>` and the member
directory as `root`; workspace patch outcomes remain available through the
root-file result fields.

Direct Copier consumers remain compatible through the default `overlay` mode.
Passing `module_name` and `domain` without a standalone package answer renders
exactly:

- `training.toml` and `study.toml`;
- `src/<module_name>/learning/{__init__,recipe,tool}.py`;
- `tests_<module_name>/unit/test_recipe.py`.

The overlay preserves `src/*/learning/recipe.py` and
`tests_*/unit/test_recipe.py` when reapplied; its configuration files remain
template-owned. The standalone route sets its mode explicitly, so adding the
public kind does not change existing overlay calls.

## Tool routing

The ordinary standalone/workspace branch passes the selected framework to the
template lookup. A regular member chooses the Python member template, while a
learning member chooses the Python learning template; research branches use
their research templates. Use Node/Svelte only for standalone creation. The
tool accepts Python, Node and Svelte; React is a check-detection framework, not
a scaffold option.

## Copier versus tool options

`CopierConfig` carries template path, destination, answer data and
`trust_template`. The scaffold tool currently enables template trust.
A template without `_tasks` can itself render without this permission, but
that is different from the tool's current invocation.

The [research template contract](research-templates.md) describes paper and
experiment answers and generated files. The [scaffold command](scaffold.md)
lists the public flags. Do not assume every Copier answer is a public flag.

## Private-package default

The Python `standalone` and `member` templates expose a Boolean Copier answer
named `private`. It defaults to `true`. With that default, the generated
`project.classifiers` list starts with the exact classifier
`Private :: Do Not Upload`; all existing classifiers retain their order after
it. Setting `private` to `false` omits only that leading classifier. The
workspace-root and research templates are unaffected.

## Workspace patch results

After member creation, `patch_all` returns `PatchReport` with `patched`,
`skipped` and `failed`. The scaffold response carries these as
`patched_root_files`, `skipped_root_files` and `failed_root_files`.
A created member can be reported successful despite failures while patching
the root; inspect those fields to assess partial integration.
