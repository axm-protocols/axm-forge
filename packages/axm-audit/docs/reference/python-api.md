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

`audit_project(package, test_reports={package.resolve(): report})` consumes a
precomputed `TestReport` for every rule declaring `runs_tests=True`. Static
rules still run normally. Passing an empty mapping refuses missing suite
evidence; it never falls back to another pytest run. Omitting `test_reports`
preserves the standalone audit behavior.

The measurement owner exports coverage JSON and pytest JSON in its own run,
using `axm_audit.core.test_runner.build_pytest_cmd`, then loads both through
`read_test_report(include_cases=True)`. These are the same builders used by
`audit_test`. The owner must bind the report to the measured tree and
environment before reusing it. A test-running rule must implement
`check_measured`; missing support fails closed.

::: axm_audit.validation_readiness

`validation_readiness(Path(...))` returns an instrument-to-cause mapping, empty
when collection and the applicable lint/type gates can run. It shares the
validation command builders, reporting dependencies, environment policy and
timeouts; it never synchronises the target environment. Code findings in lint
or type output are left to the gate; collection and environment failures refuse
admission.

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

## Session runtime

Under a transported phase contract, audit commands use its matching
DependencyEnvironment: absolute lexical interpreter, declared package root, and
declared PYTHONPATH. A local worktree virtualenv never overrides it. Runtime
package requests do not install or overlay packages in this mode; missing
instruments fail in the declared interpreter. A readable dependency path alone
does not authorize execution there. Without a contract, legacy virtualenv/uv
discovery and runtime overlays remain unchanged.
