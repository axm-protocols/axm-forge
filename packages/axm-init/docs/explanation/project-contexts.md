# Project contexts and framework selection

## Context detection

Context detection: `detect_context()` resolves five `ProjectContext` shapes — `experiment`, `paper`, `workspace`, `member`, `standalone`.

The experiment branch is evaluated FIRST, keyed on a root `manifest.yaml` whose parsed document is a mapping declaring BOTH `contract_version` and `id` (invalid YAML, a non-mapping document, a mapping missing either key, or an unreadable file all mean *not an experiment* — the predicate never raises), so an experiment nested inside a paper itself nested in a uv workspace stays an experiment.

The marker logic is split in two, mirroring the paper shape: a pure predicate over the YAML text and a thin filesystem wrapper reading the root manifest.

The paper branch is evaluated next, keyed on an explicit `[tool.axm-lab]` pyproject section OR (for a satellite paper carrying no pyproject) the full structural triple `PLAN*.md` + `paper/` + `experiments/`, all three required, so a paper nested in a uv workspace stays a paper instead of inheriting the Python-packaging rulebook.

Plus `find_workspace_root()` / `get_workspace_members()` which delegate uv-workspace resolution to `axm_ingot.uv` (`find_workspace_root` / `resolve_workspace`) and only project the result

## Skip and redirect policy

`SKIP_BY_CONTEXT` / `REDIRECT_BY_CONTEXT` map every `ProjectContext` to a frozenset of check ids — a new context is a new row, not a new branch.

`validate_context_tables()` runs at `CheckEngine` construction, so an id no discovered check declares raises `ValueError` up front instead of being a silently inert skip.

The two `experiment.*` ids are unioned into every OTHER context's skip row, derived from the registry via `_category_check_ids("experiment")` so startup validation stays green.

The `experiment` row of `REDIRECT_BY_CONTEXT` stays empty on purpose: every redirectable id is a packaging check, and the experiment context skips the packaging rulebook outright — `_filter_checks` evaluates skip before redirect, so a redirect entry there would be dead code

`SKIP_BY_CONTEXT[PAPER]` is *derived*, not hand-listed: `_known_check_ids() - _PAPER_CHECKS - _EXPERIMENT_CHECKS`.

Every Python-packaging id (Trusted Publishing, CI matrix, Diataxis nav, mkdocs, dependabot, `py.typed`, lock file, classifiers, coverage, ruff/mypy config) is therefore skipped on a paper, and a packaging check added later is skipped the day it lands.

Symmetrically the `paper.*` ids sit in the standalone, workspace and member rows, and the two `experiment.*` ids sit in all four non-experiment rows (the paper row included)

Same derivation, one context lower: `SKIP_BY_CONTEXT[EXPERIMENT]` is the union of `_PACKAGING_CHECKS` and `_PAPER_CHECKS`, both registry-derived, so no id is hand-listed and a renamed check is either routed automatically or rejected up front by `validate_context_tables()`.

A folder holding a `manifest.yaml` is not a Python distribution: `pyproject.pyproject_exists`, `structure.src_layout`, `structure.py_typed`, `structure.tests_dir`, `docs.mkdocs_exists` and the rest of the packaging rulebook never run on it, and the paper invariants belong to the paper root ABOVE it.

Only `experiment.experiment_structure` and `experiment.experiment_files` are graded — so an experiment freshly scaffolded with `--kind experiment` is reported in the `experiment` context with an EMPTY failure list, while its manifest substance (still TODO placeholders) stays axm-lab's business

## Protocol checks at the workspace root

When `CheckEngine` runs with `category="protocols"` in the `workspace`
context, it resolves uv members and selects those declaring
`[tool.axm-init.protocols]` in their metadata. Directory names do not determine
eligibility; members without that declaration are ignored.

The engine executes every discovered rule on the root and each selected member,
then aggregates results under the rule's canonical name. Component, assembly
and author-grammar failures therefore remain attributed to their own rules.
Member findings retain their file and line information, prefixed with the
member's project name (or directory name when no project name is available).
Available corrections are included in the details; a failure without details
contributes its message instead.

Each rule produces one root result, failing if the root or any selected member
fails. Its weight is the maximum of the root and member weights, rather than a
sum proportional to the number of members. Root exclusions are applied after
aggregation using the canonical name.

This responsibility belongs to category execution in the engine: new rules
participate through discovery without adding workspace branches to individual
validators. Direct calls to individual protocol validators inspect only the
supplied project; use `CheckEngine` for workspace aggregation. The category
remains explicit-only, so unfiltered checks and scores are unchanged.

See [checking workspace protocols](../howto/check.md#check-workspace-protocols)
for the command and how to follow a finding back to its member.

## What a member inherits

CI and shared tooling checks can execute against the workspace root. Others,
such as the member's docs dependency group and global reference generator,
are skipped. Redirecting a check is different from excluding it.

Context and framework are separate decisions. Framework detection recognizes
Python, Node, React and Svelte from project files; context still follows
research and uv-workspace markers. A package.json does not by itself define
a uv workspace member.

Use [grade interpretation](check-grades.md) and the
[check catalogue](../reference/checks/catalogue.md) to interpret the selected
checks. The canonical check name is also the key used by
`[tool.axm-init].exclude`.
