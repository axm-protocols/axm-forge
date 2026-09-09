# Frameworks and workspaces

## Detection

`audit_project(path)` and the `audit` tool detect the ecosystem at the target:

| Marker | Framework |
|---|---|
| `package.json` plus `svelte.config.js`, `svelte.config.ts`, or a declared `svelte` dependency/devDependency | `svelte` |
| Otherwise `package.json` with a declared `react` dependency/devDependency | `react` |
| Any other `package.json`, including an invalid JSON manifest | `node` |
| No `package.json` | `python` |

Svelte takes precedence over React. A coexisting `pyproject.toml` does not
override `package.json`. React and Svelte inherit the Node rule set;
Svelte adds `svelte-check`. React currently uses the shared Node rules.
Framework detection is manifest-based, not a full inventory of languages.

The Python API accepts `audit_project(path, framework="node")` to override
detection for a single package. The `audit` tool exposes only `path` and
`category`: it has no `framework` or `quick` argument.
Do not pass extra MCP keywords expecting an override; its `**kwargs`
currently accepts and ignores them.

## Node tooling

Node rules use the project's `node_modules/.bin` tools for ESLint,
Prettier, TypeScript, Knip and Vitest. Security checks also use npm and
Gitleaks from PATH. Install and configure the tools in the audited project.
The auditor does not run `npm install` for you. Missing tools produce findings.

`QUALITY_TYPE` runs `tsc --noEmit --pretty false`; Svelte's additional
check covers Svelte components. `QUALITY_TESTS` runs Vitest once with its
JSON reporter. Its score is the passing-test ratio; an empty suite fails.
This is different from Python coverage measurement.

The `test_quality` Node rules are structural JS/TS checks, not the Python
triage stack described in [Test Quality Rules](../test_quality.md).
`audit_test` still runs pytest, and `audit_fix` still rewrites Python tests.
They do not become Vitest/CST tools through framework detection.

## Workspace dispatch

The audit dispatcher recognizes a root without `src/` that contains
`packages/<member>/src/`. It audits those immediate members in sorted order,
using bounded parallel workers and a separate AST cache per member.
Results merge by rule ID: any member failure fails the merged check,
and scored results use the lowest member score.

This layout rule is distinct from uv dependency-hygiene workspace discovery,
which reads `[tool.uv.workspace].members`. It is not a general npm/pnpm or
recursive workspace resolver. Members without `src/` are not dispatched.

Each member is auto-detected separately. An explicit `framework=` on the
workspace root is currently not forwarded to members: target the member
directly when overriding its framework.

## Quick mode limitation

`audit_project(path, quick=True)` selects Python `LintingRule` and
`TypeCheckRule`, even when the detected or requested framework is Node,
React or Svelte. Use `category="lint"` or `category="type"` on those
frameworks. Quick mode also takes precedence over category validation.

See [configuration](configuration.md) for the separate questions of rule
settings, tool settings and environment discovery.
