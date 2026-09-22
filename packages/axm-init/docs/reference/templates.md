# Template selection

`get_template_path(template_type, framework)` selects a bundled directory
by template type and framework. Passing `None` for the framework selects Python;
unsupported resolved combinations raise `KeyError`.

| Framework | Template type | Directory |
|---|---|---|
| python | standalone | python-project |
| python | workspace | uv-workspace |
| python | member | workspace-member |
| python | paper | axm-lab provider (use paper_scaffold) |
| node | standalone | node-project |
| svelte | standalone | svelte-project |

The `protocols` profile adds metadata and declaration planning/application to
Python packages; it is not another framework template.

## Ordered template chains

`template_chain(template_type, framework, *, member)` returns an ordered tuple
of immutable `TemplateLayer` values. Each layer exposes a stable `name`, its
resolved template `path`, and the Copier answer `data` for that application.
Primitive paths are resolved through `get_template_path`; domain layers require installed providers.

Primitive types produce one layer. A standalone learning project produces
two layers in application order: `base` resolves `python-project` without a
`learning_mode` answer, then `learning` resolves `learning-project` with
`learning_mode="overlay"`. In workspace-member form, the chain contains only
the `learning` layer with `learning_mode="standalone"`.

## Learning-owned project and overlay

`template_chain(TemplateType.LEARNING, Framework.PYTHON, member=False)`
requires `axm-learning[scaffold]` and selects Learning-owned assets.
`get_template_path(TemplateType.LEARNING)` has no bundled implementation.
The template has two explicit modes over the same learning contract.

The public `init_scaffold --kind learning` route reports standalone mode when
no member is supplied, but renders the ordered `base` + `learning` chain. The
destination therefore retains the ordinary Python project's repository tooling
and metadata sections while adding `training.toml`, `study.toml`,
`src/<module_name>/learning/{__init__,recipe,tool}.py`, and the recipe unit test.
After rendering, the profile merge adds `[tool.axm-init.learning]` with a
non-empty `domain` and registers
`<module_name>.learning.tool:TrainingTool` under `axm.tools` without replacing
the composed metadata. The result reports `template="learning"`,
`profile="learning"` and `mode="standalone"`.

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
template-owned. On reruns and existing-project overlays, only the Learning layer is applied;
authored base metadata and repository tooling remain untouched.

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

## Public domain-provider API

Domain packages import scaffold primitives from `axm_init.scaffolding`:
`TemplateLayer`, `TemplateType`, `Framework`, `template_chain`, `CopierAdapter`,
`CopierConfig`, `ScaffoldResult`, `ScaffoldRequest`, `ScaffoldProvider`,
`ProviderError`, `load_provider`, and `render_scaffold`. The module also exposes
`target_root_lock`, `table_at`, and the rule primitives described below.
Init does not import domain packages directly.

A provider is installed through a zero-argument factory or class entry point:

```toml
[project.entry-points."axm.scaffold_providers"]
investigation = "my_domain.scaffolds:InvestigationProvider"
```

```python
from pathlib import Path
from axm_init.scaffolding import ScaffoldRequest, TemplateLayer


class InvestigationProvider:
    def layers(self, request: ScaffoldRequest) -> tuple[TemplateLayer, ...]:
        return (
            TemplateLayer(
                name="investigation",
                path=Path(__file__).parent / "templates" / "investigation",
                data={},
            ),
        )
```

`ScaffoldRequest` is a frozen dataclass with `kind: str`,
`framework: Framework | None = Framework.PYTHON`, `member: bool = False`,
`existing: bool = False`, and `record_answers: bool = True`.
The provider owns template selection and must return nonempty ordered layers
whose paths stay available throughout rendering. Layer names must be unique
and match `[A-Za-z0-9][A-Za-z0-9_-]*`; they identify separate Copier answers
files. `TemplateLayer.data` is `dict[str, str]` and overrides caller answers;
the caller's answer mapping may contain other object types. A provider can
compose a standard base using
`template_chain(TemplateType.STANDALONE, request.framework, member=False)`.
Do not request the provider's own kind through `template_chain` from its
`layers` method: that would recurse into discovery.

`load_provider(kind)` loads only the named entry point. It returns `None` when
absent and raises `ProviderError` for duplicate registrations, failed imports,
or a factory result without callable `layers`. A broken installed provider
never silently falls back to a bundled template. Discovery is not cached.

```python
from pathlib import Path
from axm_init.scaffolding import render_scaffold

result = render_scaffold(
    "investigation",
    Path("investigations/example"),
    {"title": "Example investigation"},
)
if not result.success:
    raise RuntimeError(result.message)
```

The full signature is
`render_scaffold(kind, destination, data, *, framework=Framework.PYTHON, member=False, record_answers=True)`.
It returns `ScaffoldResult` and uses the existing `CopierAdapter.apply_chain`.
Pass `record_answers=False` to suppress engine-generated Copier answers and
their local template paths. The option reaches provider requests and the adapter;
explicit overlay routes can also call `apply_chain(..., record_answers=False)`.
Opt-out preserves preexisting answer files, including those for the same layer.
The default continues to record a separate answer file for each layer.
It refuses a nonempty directory, file, or destination symlink before rendering,
under the shared process-local root lock. An empty directory is accepted.
Only standalone, workspace and member have bundled templates.
Learning, experiment, investigation, and other domain kinds require installed
providers; absence returns installation guidance before any write.
Templates are trusted and can execute Copier tasks. Render/task failures can
leave partial output; the operation is not transactional, and the lock does
not coordinate separate processes. Layer validation does not restrict the
behavior of trusted template tasks.

### Required domain delegation

`template_chain` requires installed `learning` and `experiment` providers.
There are no bundled Learning or Lab templates, rules, or metadata fallbacks.
`load_provider` remains a discovery API returning `None` on absence;
`require_provider` turns absence into an actionable installation error.

`init_scaffold --kind learning` retains existing-project and workspace-member
support. Its metadata/check wrappers require the corresponding provider hooks:
`declared_learning_domain`, `merge_learning_metadata`,
`register_learning_profile`, and `check_learning_profile`. Missing hooks fail
with compatible-version guidance. Providers may implement
`finalize(request, destination, data)` for metadata completion after rendering.
`ScaffoldRequest.existing` tells an overlay provider whether metadata exists.

`init_scaffold --kind experiment` is retired and returns guidance to install
axm-lab and use `experiment_scaffold`. Modern investigations and experiments
2.0 are created by Lab's ownership-aware domain tools. The shared
`render_scaffold` primitive renders provider layers; it does not replace the
domain tool's ownership and plan validation. The `legacy_experiment_layers`
hook and Learning's separate `profile_template` snapshot have been removed.

### Explicit domain rules without quality scores

`axm_init.rules` exports `run_rules`, `CheckResult`, `TomlTable`,
`requires_toml`, and `section`; these are also re-exported by
`axm_init.scaffolding`. `run_rules(path, rules)` accepts an iterable of
`Callable[[Path], T]` and returns `list[T]` in rule order. It preserves domain
finding objects, propagates rule exceptions, and performs no discovery or
score aggregation. Scientific status can therefore use domain-owned result
types without contributing to the default project quality score. Existing
learning checks remain opt-in through their explicit category.
