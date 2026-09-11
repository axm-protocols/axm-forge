<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-audit — Code auditing and quality rules for Python and JavaScript projects</strong>
</p>


<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-audit/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-audit/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-audit/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-audit/"><img src="https://img.shields.io/pypi/v/axm-audit" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

`axm-audit` audits Python, Node.js/TypeScript, React and Svelte projects.
It reports individual findings and a weighted 0–100 score when scored
measurements exist. The score describes the checks that ran; it is not a
production-readiness certificate.

## Features

- **Framework-aware audits** — Python, Node.js/TypeScript, React and Svelte checks.
- **Structured findings** — per-rule results and weighted scores through CLI,
  MCP tools and the Python API.
- **Test execution** — test verdicts, failures and optional per-case evidence.
- **Python test-tree fixes** — preview reorganizations before applying changes.
- **Documentation gate** — run a strict MkDocs build and report its findings.

<a id="install-and-run"></a>

## Installation

Requires Python 3.12+ and the target ecosystem's tooling. In a uv-managed project:

```bash
uv add axm-audit
```

The package installs the generic `axm` launcher as a dependency. Individual
checks also need the tools for the target framework; see the
[framework reference](docs/reference/frameworks.md).

## Quick Start

From the project you want to audit, run a focused lint check:

```bash
uv run axm audit . --category lint
```

The command reports the lint findings and any available score. To inspect
structured results, add `--json-output` and read the `failed` list rather
than treating a zero exit status as a passing quality gate.

## Usage

### CLI and MCP tools

The package registers `audit`, `audit_test`, `audit_fix` and `doc_gate`
under `axm.tools`. The generic `axm` CLI and AXM MCP server consume those
entry points. `verify` belongs to `axm-mcp`, which must be installed separately.

```bash
uv run axm audit . --category lint --json-output
uv run axm audit_test . --include-cases --json-output
uv run axm audit_fix .
uv run axm doc_gate .
```

`audit_fix` previews Python test-tree changes by default. Read its
[scope and rollback limits](docs/fix_pipeline.md) before using `--apply`.

A successful command means the tool produced a result. In JSON, inspect
`failed` for an audit, `verdict` for tests, and `count` for documentation
findings. A grade A can coexist with failed checks.

### Python API

```python
from pathlib import Path
from axm_audit import audit_project

result = audit_project(Path("."), category="structure")
print("Grade:", result.grade, "Score:", result.quality_score)
for check in result.checks:
    if not check.passed:
        print(check.rule_id, check.message)
```

`quality_score` and `grade` are `None` when no scored measurement exists.
The public root exports are `audit_project`, `get_rules_for_category`,
`AuditResult`, `CheckResult`, `Severity` and `__version__`.

<a id="choose-a-workflow"></a>

## Documentation

- [First audit](docs/tutorials/getting-started.md)
- [Categories and Python rules](docs/howto/categories.md)
- [Framework detection and workspace limits](docs/reference/frameworks.md)
- [CLI and tool result contracts](docs/reference/cli.md)
- [Configuration, exclusions and inheritance](docs/reference/configuration.md)
- [Scoring and grades](docs/explanation/scoring.md)
- [Test quality rules](docs/test_quality.md)
- [MCP and verify](docs/howto/mcp.md)
- [Witness quality gate](docs/reference/witness.md)
- [Python API](docs/reference/python-api.md)

The [hosted documentation](https://forge.axm-protocols.io/audit/) starts at
[docs/index.md](docs/index.md); this README is not copied into MkDocs.

<a id="documentation-and-development"></a>

## Development

This package belongs to the
[axm-forge workspace](https://github.com/axm-protocols/axm-forge).

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-packages --all-groups
uv run --package axm-audit --directory packages/axm-audit pytest
```

Running tests from the package directory selects its pytest configuration
and `tests_axm_audit/` test root. The standalone site can be built from
`packages/axm-audit` with the documentation dependencies installed:

```bash
mkdocs build --strict --site-dir /tmp/axm-audit-site
```

The root monorepo build also generates module reference pages. The standalone
site renders its own curated API page.

## License

Licensed under Apache-2.0. See [LICENSE](LICENSE).
