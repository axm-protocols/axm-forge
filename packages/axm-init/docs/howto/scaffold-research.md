# Scaffold papers and experiments

Start with an installed `axm-init` and the identity flags shown below.

## Scaffold a paper

```bash
axm init_scaffold my-paper --kind paper \
  --org myorg --author "Your Name" --email "you@example.com" \
  --description "Attention study"
```

The `paper` kind renders the paper submodule:

- `RESEARCH.md` — the research protocol: the *gap* in the literature the paper
  closes, and the *investigations* (each one the group of experiments meant to
  establish a single `objective`) declared **before** anything is measured. Its
  front-matter carries exactly `gap` and `investigations`; an investigation
  never declares a `status` — a status is a finding *derived* from the
  experiment results, never an answer given up front. The template asks for the
  gap statement (`gap_statement`) and propagates the answer verbatim into
  `gap.statement`; unanswered, it falls back to a `TODO` default, and the body
  ships marked `TODO` like the other rendered documents (`paper.research_present`
  fails while the document or its front-matter is absent)
- `PLAN.md` — the paper plan
- `PIPELINE.md` — where the data cohort comes from, what it covers and the
  command that reproduces it (skeleton to fill in; `paper.paper_structure`
  fails while it is absent)
- `README.md`
- `paper/` — `main.tex`, `references.bib` and its `Makefile`
- `experiments/` — the root every experiment lands in
- `pyproject.toml` carrying `[tool.axm-lab]`, the marker that makes the
  directory a *detected paper*

## Scaffold an experiment inside a paper

```bash
axm init_scaffold my-paper --kind experiment --name baseline \
  --org myorg --author "Your Name" --email "you@example.com"
```

The `experiment` kind:

1. Refuses any target that is not a detected paper — it fails **before writing
   anything**, so a mistyped path never leaves debris
2. Names the directory itself, with the next free zero-padded index and the
   slugified `--name`: `experiments/01-baseline/`, then `experiments/02-…`
3. Renders the experiment scaffold flat inside it — `manifest.yaml` (the 1.1.0
   experiment declaration, written before any script runs), `inputs/`, `scripts/`,
   `outputs/`, `analysis/analysis.md` and `figures/figures.yaml`

> **Note:** `figures/figures.yaml` is the figure declaration the experiment
> contract reads — it ships as an empty declaration with a commented skeleton
> naming the `id`, `caption`, `script` and `reads` keys. `analysis/analysis.md`
> is the end-of-experiment reading, filled once the outputs exist; the metrics
> file beside it (`analysis/metrics.yaml`) is emitted by the run, never
> scaffolded.

> **Note:** the index belongs to the tool, never to the template — re-running
> the command always allocates the next free slot.


## Tool defaults versus Copier answers

The paper command uses the autonomous template defaults (`has_package=true`);
it does not expose `has_package` or `gap_statement` as CLI options.
The experiment command uses `type=descriptive` and
`reproduction_level=tolerance`; its public options do not select those answers.

The [research template reference](../reference/research-templates.md) describes
the other Copier variants. A valid scaffold establishes form, not a completed
research protocol or verified experiment.

For the default `tolerance` reproduction level, add the actual `bounds` required
by axm-lab before validating the manifest there. The current template does not
supply them; see [manifest completion](../reference/research-templates.md#completing-the-default-manifest).
