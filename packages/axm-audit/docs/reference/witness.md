# Audit quality witness

`axm-audit` registers `AuditQualityRule` as `audit_quality` under
`axm.witnesses`. This is independent of `axm.tools` and of Git
pre-commit/prek hooks. It is not a YAML HookAction.

The implementation is importable from
`axm_audit.witnesses.audit_quality`; it is not a root-package export.

| Parameter | Default | Meaning |
|---|---|---|
| `categories` | `["lint", "type"]` | Audit categories evaluated independently |
| `working_dir` | `"."` | Project root; overridable in `validate(..., working_dir=...)` |
| `guidance` | `None` | Extra remediation text appended on failure |
| `scope` | `"."` | Reserved; currently unused |
| `exclude_rules` | `[]` | Prefixes removed from the returned failure list |
| `extra_dirs` | `[]` | Additional project directories audited with the same categories |

An invalid directory, unknown category, empty categories list, or exceptions
from all requested category calls produce a failed witness. Actual audit failures
are formatted with `format_agent` and retained in witness metadata.

Limits matter for quality gates: a category that raises is logged and
omitted when another category succeeds. Missing extra directories are
skipped, and exceptions in extra-directory audits are logged. Thus this
witness is not a completeness guarantee for every requested scope.
Exclusions change the failure list without recomputing the score.

See [categories](../howto/categories.md) and the rendered
[implementation reference](python-api.md#witness).
