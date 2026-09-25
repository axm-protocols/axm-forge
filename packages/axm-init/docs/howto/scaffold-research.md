# Scaffold papers and research

Install axm-lab to create a paper from existing local venue and edition inputs:

```bash
axm paper_scaffold --workspace /path/to/papers --venue example-symposium \
  --year 2026 --slug attention-study --title "Attention study"
```

The venue must have `PROFILE.md`; the year must have `EDITION.yaml` and a local
template. Lab validates and snapshots these inputs. Complete `PLAN.md`,
`PIPELINE.md`, and the sources in `paper/`, then run `axm paper_check --path PATH`.
This creates no investigation or experiment. Init's former `--kind paper`
entrypoint returns routing guidance and has no fallback template.

Install axm-lab for research operations. Create an investigation with
`investigation_scaffold`, declare the experiment in its plan, and use
`experiment_scaffold` to create the modern 2.0 experiment under that owner.
Use Lab's `experiment_check` for validation. Forge's former experiment scaffold
and checks now return explicit migration guidance.

When the paper selects its investigations and evidence, author a downstream
`research.yaml` selection. Lab remains the authority for investigation plans,
experiment manifests, and evidence. See the [research scaffold boundary](../reference/research-templates.md).
