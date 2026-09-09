# Python API

The root exports below are the package's external Python surface.
Rule implementation modules, formatters, tools and the witness are separately
importable but are not re-exported at the root.

The monorepo build already generates per-module pages under
`reference/axm_audit/`. This curated page renders in both standalone and
monorepo builds and makes the entry points discoverable in navigation.

## Audit entry points

::: axm_audit.audit_project

::: axm_audit.get_rules_for_category

## Result models

::: axm_audit.AuditResult

::: axm_audit.CheckResult

::: axm_audit.Severity

`axm_audit.__version__` is a string supplied by the build's VCS version hook.

## Formatters and exceptions

::: axm_audit.formatters
    options:
      members:
        - format_report
        - format_json
        - format_agent
        - format_agent_text
        - format_test_quality_text
        - format_test_quality_json

::: axm_audit.score.ScoreIncalculableError

## Tool implementations

::: axm_audit.tools.audit.AuditTool.execute

::: axm_audit.tools.audit_test.AuditTestTool.execute

::: axm_audit.tools.audit_fix.AuditFixTool.execute

::: axm_audit.doc_gate.tool.DocGateTool.execute

## Witness

::: axm_audit.witnesses.audit_quality.AuditQualityRule
    options:
      members: [validate]

For exact transport behavior, parameter tables and known limits, use the
[CLI/tools reference](cli.md), [results guide](../howto/results.md) and
[framework reference](frameworks.md). Source docstrings can lag the runtime;
the narrative describes the checked behavior.
