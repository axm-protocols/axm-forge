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
| node | standalone | node-project |
| svelte | standalone | svelte-project |

The `protocols` profile adds metadata and declaration planning/application to
Python packages; it is not another framework template.

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

## Workspace patch results

After member creation, `patch_all` returns `PatchReport` with `patched`,
`skipped` and `failed`. The scaffold response carries these as
`patched_root_files`, `skipped_root_files` and `failed_root_files`.
A created member can be reported successful despite failures while patching
the root; inspect those fields to assess partial integration.
