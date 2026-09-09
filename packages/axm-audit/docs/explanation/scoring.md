# Scoring and verdicts

## Composite quality score

`AuditResult.quality_score` averages numeric check scores within each
category, then computes a weighted average across the categories present.
Checks with `score=None` do not enter that average.

| Category | Weight |
|---|---|
| lint | 15 |
| type | 15 |
| complexity | 15 |
| security | 10 |
| deps | 10 |
| testing | 10 |
| test_quality | 10 |
| architecture | 10 |
| practices | 5 |

`structure` and `tooling` emit findings without a composite weight.

```text
score = round(sum(category_average * weight) / sum(present_weights), 1)
```

A single scored category is therefore a valid score, normalized to 100.
When no numeric scored category remains, `quality_score` and `grade`
are `None`. An absent category and a failed check are different:
a rule exception becomes a failed check with score zero and crash metadata.
`AuditResult.crashed_rules` exposes those rule IDs.

A score can still omit a failed check whose rule returned no numeric score.
Always inspect failures and unavailable measurements alongside the number.

## Grading scale

| Grade | Score |
|---|---|
| A | ≥ 90 |
| B | ≥ 80 |
| C | ≥ 70 |
| D | ≥ 60 |
| F | < 60 |
| None | No calculable score |

A grade is a summary of measurements, not a deployment or safety verdict.
`AuditResult.success` is `all(check.passed for check in checks)`;
it does not test the grade or ignore warning-severity failures.
With no checks this expression is true, so callers needing evidence must
also verify that the intended checks ran.

## Rule scores are not universal pass thresholds

| Python check | Numeric score | Pass condition |
|---|---|---|
| Lint | `max(0, 100 - 2 * issues)` | No lint issues (`LINT_PASS_THRESHOLD=100`) |
| Type | `max(0, 100 - 5 * errors)` | No type errors and a usable environment |
| Complexity | `max(0, 100 - 10 * offenders)` | Score ≥ 90 |
| Private imports | `max(0, 100 - 5 * findings)` | No findings |
| Tautology | `max(0, 100 - 2 * counted_findings)` | No counted findings |
| Duplicate tests | `max(0, 100 - 5 * clustered_pairs)` | No counted pairs |
| Formatting | `max(0, 100 - 5 * unformatted_files)` | Score ≥ 90 |
| Bandit | `max(0, 100 - 15 * high - 5 * medium)` | Score ≥ 90 |
| Known dependency vulnerabilities | `max(0, 100 - 15 * vulnerable_packages)` | Score ≥ 90 when measured |
| Coupling | `max(0, 100 - 3 * warnings - 5 * errors)` | No coupling errors |
| Bare except | `max(0, 100 - 20 * findings)` | No findings |
| Blocking I/O patterns | `max(0, 100 - 15 * findings)` | No findings |

Thus one type error may yield score 95 and grade A while the check fails.
Complexity flags radon rank C or higher (CC ≥ 11), or cognitive complexity
strictly greater than 15. A block exceeding both counts once. This describes
the implemented thresholds; a project's own policy may be stricter.

Category scores average the registered scored rules that actually ran;
there is no permanent four-rule denominator for practices or test quality.
Frameworks can share a rule ID with different measurements: Node
`QUALITY_TESTS` is a Vitest pass ratio, while Python uses suite/coverage
evidence. See [frameworks](../reference/frameworks.md) and
[test quality](../test_quality.md).

## Unavailable and partial measurements

Current behavior is not uniformly fail-closed. In particular,
`DependencyAuditRule` treats a classified transient PyPI/network failure as
`passed=True`, score 100, warning severity and a skipped-scan message. That
is a skipped measurement, not evidence of no vulnerabilities.
Dependency-hygiene member errors can also be omitted from workspace issue
aggregation. Review availability messages and required scope in addition
to the grade and failure list.

Diff-size measurement uses uncommitted `git diff --stat HEAD`, not a branch
comparison and not untracked file contents. Its score is 100 at/below the
configured ideal, zero at/above the configured maximum, and decreases
linearly between them (defaults 400 and 1200 lines).

Python coverage comes from pytest-cov. Its per-file gap list excludes files
named `__main__.py`, while the measured aggregate is not rewritten. To also
exclude those files from the aggregate, configure coverage itself.

## Serialization: strict and tolerant surfaces

| Surface | No calculable score |
|---|---|
| `AuditResult.quality_score`, `.grade` | `None` |
| `format_agent`, `format_test_quality_json` | Null score/grade |
| `format_agent_text` | Omits the score/grade segment |
| `format_json` | Raises `ScoreIncalculableError` |
| `audit` tool / CLI JSON | Tolerates null score/grade via `format_agent` |

`format_json` is not the serializer used by CLI `--json-output`.
Both strict and tolerant formatter paths share the score resolver.

## Severity and tool success

Severity describes a finding's impact. The `passed` flag determines
whether that check contributes a failure. Warning and information
severities are not universal exemptions.

A successful audit tool invocation can contain failed checks.
A successful `audit_test` invocation can measure failing tests.
Use the [tool-specific verdict fields](../reference/cli.md) for automation.
