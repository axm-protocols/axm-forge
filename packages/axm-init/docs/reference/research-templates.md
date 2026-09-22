# Research scaffold boundary

Forge bundles the paper writing scaffold. `TemplateType.PAPER` resolves
`paper-submodule`; `has_package` selects an autonomous Python package or a
satellite writing tree. Both render `PLAN.md`, `PIPELINE.md`, `README.md`, and
`paper/` with LaTeX sources, bibliography, and a Makefile. Satellite detection
uses `PLAN*.md` plus `paper/`; no experiment directory is required.

Paper scaffolds contain no `RESEARCH.md`, flat `experiments/` root, generated
index, or fabricated research selection. After investigations and evidence are
selected, author downstream `research.yaml` using Lab's current contract.

Lab exclusively owns investigations and experiments 2.0. Install axm-lab and
use `investigation_scaffold` / `experiment_scaffold`; the domain tools validate
ownership and plan state before invoking Forge's shared rendering engine.
`init_scaffold --kind experiment` refuses with migration guidance. No 1.x
experiment templates or experiment form rules remain in Forge.

Learning owns its templates, metadata, and rules through the installed
`axm-learning[scaffold]` provider. See [template selection](templates.md).
Removed assets remain recoverable from Git history.
