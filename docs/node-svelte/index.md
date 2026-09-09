# Node, React and Svelte support

Forge's tools run in Python. Some also analyse or scaffold JS/TS projects.
Support depends on the operation; selecting a framework does not turn every
Python tool into its Node counterpart.

## Current usage

| Need | Current documentation |
|---|---|
| Audit a Node, React or Svelte project | [Framework detection and tooling](../audit/reference/frameworks.md) |
| Scaffold a Node or Svelte project | [Template selection](../init/reference/templates.md) |
| Inspect source structure | [axm-ast](../ast/index.md), with its optional TypeScript support |
| Understand limits of test-quality checks | [Audit test quality](../audit/test_quality.md) |

Audit detection prioritises Svelte, then React, when their markers occur in a
`package.json` project. React and Svelte inherit Node rules; Svelte has
an additional check. The current `audit` tool accepts `path` and
`category`, not a `framework` override. The Python audit API has a
separate override contract.

Scaffolding supports Node/Svelte standalone templates. Python workspace and
member templates have their own route. `audit_test` remains a pytest
runner and `audit_fix` a Python test refactoring tool.

Use the linked package references for exact options, required tools and
limitations.
