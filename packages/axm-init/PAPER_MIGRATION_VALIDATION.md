# Paper ownership migration

Removed the bundled paper-submodule template and paper rule module. Lab now owns
edition-aware paper creation and writing/frozen-provenance checks. Obsolete Init
paper requests fail explicitly before identity lookup or optional PyPI probing;
there is no paper fallback. Generic provider rendering and Learning behavior are
preserved. Paper context detection remains solely for actionable routing.

TDD: test_paper_retired.py initially failed twice because the old template resolved
and paper remained in ALL_CHECKS. The final tests additionally assert early
entrypoint refusal without identity or network access.

From this Forge feature checkout, using the environment installed from matching
Init, Lab, Learning and Doctor feature sources:

```bash
PATH="/home/gjarry/orca/workspaces/axm-knowledge/feat-investigation-scaffolds/.venv/bin:$PATH" \
  /home/gjarry/orca/workspaces/axm-knowledge/feat-investigation-scaffolds/.venv/bin/pytest \
  -q -o addopts='' packages/axm-init/tests_axm_init
```

Final result: **1114 passed, 1 skipped in 75.69s**. Python/Node/workspace and
Learning provider coverage passes. Changed Python files pass Ruff and
`git diff --check`. A targeted mypy run reports only the existing two explicit-Any
errors in scaffolding.py provider_hook's Callable declarations; these declarations
were unchanged.

Lab's companion PAPER_SCAFFOLD_VALIDATION.md records dependency installation,
all red/green commands, the 532-test Lab suite, and successful actual installed
CLI smoke using a temporary copy of current OpenSky inputs. No original workspace
was changed by this worker. The upstream locale-dependent digest was independently
corrected by the coordinator; Lab accepts only the documented canonical digest.
