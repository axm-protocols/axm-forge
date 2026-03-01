# Glossary

Technical terms used throughout the `axm-audit` documentation.

## Tools

| Term | Definition |
|---|---|
| **Ruff** | An extremely fast Python linter and formatter written in Rust. Replaces flake8, isort, pyupgrade, and others |
| **mypy** | A static type checker for Python that enforces type annotations at development time |
| **radon** | A Python tool that computes code complexity metrics, including cyclomatic complexity |
| **Bandit** | A security linter for Python that finds common security issues in source code |
| **pip-audit** | A tool that scans Python dependencies for known vulnerabilities (CVEs) |
| **deptry** | A tool that detects missing, unused, and transient dependencies in Python projects |
| **pytest-cov** | A pytest plugin that measures code coverage during test execution |

## Metrics

| Term | Definition |
|---|---|
| **Cyclomatic complexity** | A quantitative measure of the number of linearly independent paths through a function's source code. Higher values indicate more complex, harder-to-test code. `axm-audit` flags functions at CC ≥ 10 |
| **Fan-out** | The number of modules that a given module imports. High fan-out (> 10) indicates tight coupling |
| **God class** | A class that has grown too large, accumulating too many responsibilities. Typically detected by method/attribute count |
| **Coupling** | The degree of interdependence between modules. Lower coupling makes code easier to maintain and test |
| **Test mirroring** | A convention where every source module `src/pkg/foo.py` has a corresponding test file `tests/test_foo.py` |

## Concepts

| Term | Definition |
|---|---|
| **Composite score** | The weighted average of all 8 category scores, producing a single 0–100 quality metric |
| **Pass threshold** | The minimum score (90/100) for an individual check to be marked as passing |
| **Severity** | The impact level of a finding: `error` (blocks pass), `warning` (non-blocking), `info` (informational) |
| **ProjectRule** | The abstract base class that all audit rules inherit from. Defines the `rule_id` property and `check()` method |
| **CheckResult** | A Pydantic model representing the outcome of a single rule check, including pass/fail, message, severity, and details |
| **AuditResult** | A Pydantic model containing all check results, the composite score, and the letter grade |
| **Diátaxis** | A documentation framework that organizes content into four quadrants: Tutorials, How-to guides, Reference, and Explanation |
