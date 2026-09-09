# Research template contracts

The bundled Copier templates describe the rendered files and answer choices.
Public tool flags expose only a subset of those answers.

## Paper template

`TemplateType.PAPER` resolves `paper-submodule`. The `has_package` answer
selects two variants:

| Variant | Rendered boundary |
|---|---|
| Autonomous | Own `src/` package and a `[tool.axm-lab]` pyproject marker |
| Satellite | No pyproject or source package; identified structurally by `PLAN.md`, `paper/` and `experiments/` |

The paper tool supplies `paper_name`, `title` and `author`, retaining
`has_package=true`. Neither `has_package` nor `gap_statement` is a public
`init_scaffold` flag. See the [research guide](../howto/scaffold-research.md)
for the generated research, plan and provenance documents.

The template declares no Copier `_tasks`, so it can render without template
trust; the current tool nevertheless passes `trust_template=True`.

## Experiment manifest

`TemplateType.EXPERIMENT` resolves `experiment`. An experiment is created
inside a detected paper. Its declaration exists before scripts run.

| Field | Rendered contract |
|---|---|
| `contract_version` | Explicit quoted string `"1.1.0"` |
| `id`, `title`, `question` | Pre-filled identity and research question |
| `type` | `hypothesis_testing`, `descriptive`, or `exploratory` |
| `repro_level` | `exact`, `tolerance`, or `attested` |
| `inputs`, `steps` | Initial declarations |
| `supports` | Empty list of investigation identifiers at scaffold time |
| `falsifier` | Only for `hypothesis_testing`: mapping with `spec` and `conditions` |

The five Copier answers are `experiment_id`, `experiment_title`,
`research_question`, `type` and `reproduction_level`.
The public tool supplies identity, title and question, retaining
`type=descriptive` and `reproduction_level=tolerance`.

`supports` records the investigations served by the experiment, complementary
to their grouping in the paper. axm-init renders this list without validating
its references.

The axm-lab model requires a version field but does not constrain its string
value: `"1.0.0"` and an omitted `supports` remain accepted at those fields,
subject to every other model invariant. This is not a promise that an arbitrary
old manifest is valid.

## Files and evidence

The template renders flat at its destination. The tool owns the experiment
directory name and index; the template does not nest another experiment folder.

| Path | Role |
|---|---|
| `README.md`, `inputs/SOURCES.md` | Experiment description and source inventory |
| `scripts/`, `outputs/` | Execution code and produced outputs |
| `analysis/analysis.md` | End-of-experiment interpretation, completed after outputs exist |
| `figures/figures.yaml` | Empty figure declaration `[]` with a commented skeleton naming `id`, `caption`, `script`, `reads` |
| `freeze/model_spec.json` | Pre-registration artifact, only for `hypothesis_testing` |
| `.gitignore` | Cache/virtualenv exclusions; evidence remains versioned |

`figures/figures.yaml` replaced an unused `figures/FIGURES.md` prose index.
No fake figure is emitted. No metrics file is scaffolded:
`analysis/metrics.yaml`, consumed by axm-lab, records machine-produced findings
after execution. Freeze artifacts stay tracked so downstream checks can inspect
pre-registration ancestry in git.

## Completing the default manifest

The current axm-lab `ExperimentManifest` requires `bounds` when
`repro_level="tolerance"`. The axm-init template selects tolerance by default
but does not render bounds. Supply the experiment's actual tolerance bounds
before validating or running it through axm-lab; the default scaffold is not
a fully validated experiment contract.

For hypothesis testing, the template emits a falsifier mapping shaped as
`{spec: "<non-empty string>", conditions: []}`. The authoritative `Falsifier`
model forbids extra fields but declares `spec` as a string without a
minimum-length validator. A non-empty template placeholder is not evidence
that a useful falsifier has been written.

axm-init owns the rendered tree, keys and answer choice sets. Authoritative
manifest validation belongs to axm-lab, with no dependency between the two
packages. Passing the [form checks](checks/catalogue.md) only verifies the
expected files/directories and document headers.

## Template maintenance

Copier replaces rather than extends its default `_exclude` list. These
bundled templates therefore re-declare the complete exclusion block.

The answer named `type` also appears in the conditional `freeze/` directory
name. Renaming that answer independently from its use in the path can render an
empty directory name and silently omit the directory. The empty-path Jinja
idiom is intentional: it emits the freeze artifact only for hypothesis testing.
