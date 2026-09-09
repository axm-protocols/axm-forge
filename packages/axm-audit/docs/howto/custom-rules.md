# Write a custom rule

The rule engine is extensible in process through
`axm_audit.core.rules.base.ProjectRule` and `register_rule`.
These are implementation-module APIs, not root exports.
A decorator takes effect only when the defining module is imported:
installing an arbitrary package does not make its rules discoverable.

## A complete rule

This rule checks for a changelog policy document and joins the existing
unscored `structure` category. Run it in the process that imports the class.

```python
from pathlib import Path
from axm_audit import audit_project, CheckResult, Severity
from axm_audit.core.rules.base import ProjectRule, register_rule

@register_rule("structure")
class ChangelogPolicyRule(ProjectRule):
    @property
    def rule_id(self) -> str:
        return "STRUCTURE_CHANGELOG_POLICY"

    def check(self, project_path: Path) -> CheckResult:
        present = (project_path / "CONTRIBUTING.md").is_file()
        return CheckResult(
            rule_id=self.rule_id,
            passed=present,
            message="CONTRIBUTING.md exists" if present else "Add CONTRIBUTING.md",
            severity=Severity.INFO if present else Severity.ERROR,
        )

result = audit_project(Path("."), category="structure")
assert any(c.rule_id == "STRUCTURE_CHANGELOG_POLICY" for c in result.checks)
```

Use a known category when selecting it through `audit_project(category=...)`.
`register_rule("custom")` alone does not extend the auditor's category
allow-list or assign that new category a composite weight.

## Scored rules

Set `CheckResult.score` directly, not `details["score"]`.
`passed` is a separate decision: choose a clear invariant for your rule.
The common threshold constant is 90, but built-in lint/type and several
test-quality rules require zero findings. A category is injected when the
auditor executes the rule; a direct `rule.check(path)` call does not do that.

The optional `framework=` argument on `register_rule` chooses the
registry bucket. It defaults to Python. Node-derived UI frameworks inherit
the Node registry before adding their own rules.

## External tools

Use `run_in_project(cmd, path, capture_output=True, text=True)` when
a Python rule needs captured stdout. Its defaults do not capture output.
Validate the return code and output before awarding a score; a missing tool
or invalid JSON must not become a clean measurement.

The runner finds the nearest environment, may use uv runtime packages,
and returns synthetic exit 124 on timeout unless `check=True` requests
an exception. Its default timeout is 300 seconds. See
[configuration](../reference/configuration.md) for the complete scope.

Configuration examples for coupling, coverage and exemptions live in the
[configuration reference](../reference/configuration.md).
