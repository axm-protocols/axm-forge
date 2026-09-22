# Project contexts and framework selection

## Context detection

Context detection: `detect_context()` resolves five `ProjectContext` shapes — `experiment`, `paper`, `workspace`, `member`, `standalone`.

The experiment branch is evaluated FIRST, keyed on a root `manifest.yaml` whose parsed document is a mapping declaring BOTH `contract_version` and `id` (invalid YAML, a non-mapping document, a mapping missing either key, or an unreadable file all mean *not an experiment* — the predicate never raises), so an experiment nested inside a paper itself nested in a uv workspace stays an experiment.

The marker logic is split in two, mirroring the paper shape: a pure predicate over the YAML text and a thin filesystem wrapper reading the root manifest.

The paper branch recognizes `PLAN*.md` plus `paper/`. An existing explicit
`[tool.axm-lab]` marker remains recognizable, but new writing scaffolds do not
create Lab metadata. Paper detection applies before workspace membership.

`find_workspace_root()` and `get_workspace_members()` use `axm_ingot.uv`.

## Skip and redirect policy

`SKIP_BY_CONTEXT` and `REDIRECT_BY_CONTEXT` select applicable packaging and
paper writing checks. `validate_context_tables()` rejects unknown check IDs.
Paper projects run their writing-layout and PLAN checks; standalone and
workspace projects exclude paper checks. Members inherit applicable root CI
and tooling checks.

Experiment detection is retained to return actionable guidance: Forge refuses
experiment validation and directs callers to axm-lab's `experiment_check`.
It has no bundled experiment checks and does not return an empty passing grade.

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
