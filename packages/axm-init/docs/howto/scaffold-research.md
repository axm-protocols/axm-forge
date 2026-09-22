# Scaffold papers and research

Create the paper writing scaffold:

```bash
axm init_scaffold my-paper --kind paper \
  --org myorg --author "Your Name" --email "you@example.com" \
  --description "Attention study"
```

Complete `PLAN.md`, `PIPELINE.md`, and the sources in `paper/`. This creates no
Lab research authority, `RESEARCH.md`, or flat experiment root.

Install axm-lab for research operations. Create an investigation with
`investigation_scaffold`, declare the experiment in its plan, and use
`experiment_scaffold` to create the modern 2.0 experiment under that owner.
Use Lab's `experiment_check` for validation. Forge's former experiment scaffold
and checks now return explicit migration guidance.

When the paper selects its investigations and evidence, author a downstream
`research.yaml` selection. Lab remains the authority for investigation plans,
experiment manifests, and evidence. See the [research scaffold boundary](../reference/research-templates.md).
