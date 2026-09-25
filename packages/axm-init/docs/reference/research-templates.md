# Research scaffold boundary

Lab owns paper, investigation and experiment templates and rules. Install
`axm-lab` and use `paper_scaffold`, `paper_check`, `investigation_scaffold`,
and `experiment_scaffold`. Paper creation requires local venue PROFILE.md,
year EDITION.yaml and a selected edition template; it may precede investigations.

Init supplies the generic provider rendering and checking primitives plus
Python, Node and workspace support. It bundles no paper or experiment template.
`init_scaffold --kind paper` and `--kind experiment` fail with routing guidance;
`init_check` similarly redirects paper/experiment contexts to Lab.
The generic `render_scaffold("paper", ...)` is a low-level provider seam; callers
should use Lab’s public tool to validate and snapshot edition inputs.

Learning owns its templates, metadata and rules through the installed
`axm-learning[scaffold]` provider. See [template selection](templates.md).
