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
| python | learning | learning-profile |
| node | standalone | node-project |
| svelte | standalone | svelte-project |

The `protocols` profile adds metadata and declaration planning/application to
Python packages; it is not another framework template.

## Learning overlay

`TemplateType.LEARNING` with `Framework.PYTHON` selects `learning-profile`.
This is a Copier overlay for an existing Python project, not a complete project
template: it does not render `pyproject.toml`, a README, a licence or workspace
metadata. Its required answers are `module_name` (the Python import name) and
`domain` (the short learning-domain identifier).

A render produces exactly:

- `training.toml` and `study.toml`;
- `src/<module_name>/learning/{__init__,recipe,tool}.py`;
- `tests_<module_name>/unit/test_recipe.py`.

The generated recipe fabricates deterministic data in memory, while the tool
module delegates training to the delivered `axm-fit` engine. Reapplying the
overlay preserves `src/*/learning/recipe.py` and
`tests_*/unit/test_recipe.py`; the configuration files remain template-owned.
The scaffold command does not route a public learning option yet, so selecting
this overlay currently requires the Python template API and Copier adapter.

## Tool routing

The ordinary standalone/workspace branch passes the selected framework to the
template lookup. The current member branch always chooses the Python member
template; research branches use their research templates. Use Node/Svelte only
for standalone creation. The tool accepts Python, Node and Svelte; React is a
check-detection framework, not a scaffold option.

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
