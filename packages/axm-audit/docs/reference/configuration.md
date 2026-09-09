# Configuration and exclusions

## Three independent scopes

Rule options below are read from the audited package's `pyproject.toml`.
These readers do not merge a parent workspace's `[tool.axm-audit]` table.
Put member-specific settings in each member.

External tools use their own configuration discovery: Ruff, mypy, coverage,
ESLint and TypeScript are not configured by one shared AXM exclusion list.
For example, a Ruff exclusion does not imply that the Python complexity
walker skips the same file.

Environment discovery is separate again. Python subprocess rules use
`run_in_project`, which searches for the nearest `.venv/`, including
ancestors. With an environment or requested runtime packages it invokes
`uv run --directory`; without a venv, requested packages use
`uv run --isolated`. Otherwise it invokes the command from PATH with the
project as cwd. Ordinary uv execution may synchronize the target environment.

## Python rule options

```toml
[tool.axm-audit]
diff_size_ideal = 400
diff_size_max = 1200

[tool.axm-audit.coverage]
min_coverage = 90

[tool.axm-audit.coupling]
fan_out_threshold = 10
orchestrator_bonus = 5
severity_error_multiplier = 2

[tool.axm-audit.coupling.overrides]
"my_package.hub" = 20
"registry" = 25

[tool.axm-audit.mirror]
exempt_paths = ["schemas/*.py", "**/_facade.py"]
exempt_tests = ["conformance/**", "contracts/*.py"]

[tool.axm-audit.duplicate_tests]
exempt_paths = ["tests/generated/**"]

[[tool.axm-audit.duplicate_tests.acknowledged]]
hash = "a1b2c3d4e5f6"
reason = "Reviewed: these tests exercise distinct contracts"
```

The values shown are defaults except for overrides and exemptions, which are
examples. Coupling overrides match exact module names or suffixes.
The severity multiplier is clamped to at least 1. Modules above the effective
fan-out threshold but within threshold × multiplier produce coupling warnings
(three points each); larger excesses produce errors (five points each).
Warnings alone do not fail that coupling check. The effective threshold can
include an orchestrator bonus as well as a module override.

Coverage accepts numeric
values in [0, 100], falling back to 90 for an invalid value; zero removes
the coverage percentage threshold, not other suite failure conditions.

Mirror `exempt_paths` globs are anchored at `src/<package>/`;
`exempt_tests` globs are anchored at `tests/unit/`. The former suppresses
missing source mirrors, the latter orphan tests. Neither replaces the other.
`*` and `?` do not cross path separators; a `**` segment spans segments.

Duplicate-test exemptions use project-relative test paths. Acknowledgements
accept a particular cluster hash; changed membership can make the hash stale.
Stale acknowledgements remain observable in metadata. Invalid acknowledgement
configuration is reported as metadata, not a general configuration exception.

Malformed TOML and wrong values are not handled uniformly across readers:
mirror list/schema errors can fail the mirror rule; other threshold readers
fall back for the invalid values they handle. Do not assume every malformed
nested table is safe or that every unused key is rejected.

## Rule-specific and external-tool exclusions

There is no general `exclude_rules` argument on the `audit` tool.
Use `category` to select a category. The witness has its own
[rule-prefix failure filter](witness.md), which does not remove those
measurements from the numeric score.

- Ruff follows its configuration; lint/type targets include `src/` and the
  resolved suite directory.
- Python complexity walks `src/**/*.py` independently.
- Duplicate collection excludes fixture corpus trees; its own globs add
  further exclusions.
- Intentional test markers are documented in [Test Quality Rules](../test_quality.md).
  Register markers in pytest when using `--strict-markers`.

Several Python test-quality paths and the fix rollback still explicitly
expect `tests/`. In particular, file naming and no-package-symbol checks
return early when that directory is absent. A package using only
`tests_axm_<name>/` must not treat those skipped checks as evidence that
the custom test tree was audited. Lint/type suite resolution does not imply
the same support in every rule. See [fix limits](../fix_pipeline.md).

## Tools and timeouts

Python lint injects Ruff at runtime. Type checking deliberately uses the
target environment's mypy, so install mypy and relevant type stubs there.
Other rules may request their own runtime tools; injection can require
network/cache access.

`run_in_project` defaults to 300 seconds. The structured pytest runner
uses 900 seconds; `doc_gate` defaults to 120. These are not one global
timeout and not every direct subprocess in every rule uses the shared runner.

Node tools have their own local/PATH resolution, described in
[frameworks](frameworks.md).
