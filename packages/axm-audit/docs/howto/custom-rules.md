# Write Custom Rules

Extend `axm-audit` with your own project-specific rules.

## The `ProjectRule` base class

Every rule inherits from `ProjectRule`, an abstract base class with two requirements:

```python
from abc import ABC, abstractmethod
from pathlib import Path

from axm_audit.core.rules.base import ProjectRule
from axm_audit.models.results import CheckResult

class MyRule(ProjectRule):
    @property
    def rule_id(self) -> str:
        """Unique identifier — by convention: CATEGORY_NAME."""
        return "CUSTOM_MY_CHECK"

    def check(self, project_path: Path) -> CheckResult:
        """Run the check and return a result."""
        # Your logic here
        return CheckResult(
            rule_id=self.rule_id,
            passed=True,
            message="All good",
            severity="info",
        )
```

!!! note "Contract"
    - `rule_id` → `@property` returning a unique `str` (e.g. `CUSTOM_README_LENGTH`)
    - `check(project_path)` → returns a `CheckResult` with pass/fail, message, severity, and optional `details`/`text`/`fix_hint`

## Scoring conventions

Rules follow a consistent scoring pattern:

| Pattern | Formula | Example |
|---|---|---|
| **Penalty-based** | `max(0, 100 - count × penalty)` | 10 lint issues × 2 = score 80 |
| **Ratio-based** | `int(coverage × 100)` | 95% docstrings = score 95 |
| **Binary** | 100 or 0 | File exists or not |

Pass threshold: **score ≥ 90** (defined as `PASS_THRESHOLD` in `base.py`).

## Using `run_in_project()`

For rules that call external tools:

```python
from axm_audit.core.runner import run_in_project

class MyToolRule(ProjectRule):
    @property
    def rule_id(self) -> str:
        return "CUSTOM_MY_TOOL"

    def check(self, project_path: Path) -> CheckResult:
        result = run_in_project(
            ["my-tool", "check", "src/"],
            project_path,
            timeout=60,
        )
        issues = int(result.stdout.strip() or "0")
        score = max(0, 100 - issues * 5)
        return CheckResult(
            rule_id=self.rule_id,
            passed=score >= 90,
            message=f"Score: {score}/100 ({issues} issues)",
            severity="warning" if score < 90 else "info",
            details={"score": score, "issues": issues},
            fix_hint="Run: my-tool fix src/" if issues > 0 else None,
        )
```

`run_in_project()` automatically:

- Detects the project's `.venv/`
- Runs via `uv run --directory`
- Applies a 300-second timeout (configurable)
- Returns a synthetic `returncode=124` on timeout

## Registering your rule

Use the `@register_rule` decorator to add your rule to the auto-discovery registry:

```python
from axm_audit.core.rules.base import register_rule, ProjectRule

@register_rule("custom")
class MyRule(ProjectRule):
    @property
    def rule_id(self) -> str:
        return "CUSTOM_MY_CHECK"

    def check(self, project_path: Path) -> CheckResult:
        ...
```

The decorator registers the rule and auto-injects the `category` property.

Or run it standalone:

```python
rule = MyRule()
result = rule.check(Path("/path/to/project"))
print(f"{'✅' if result.passed else '❌'} {result.message}")
```

## Configuring coupling thresholds

The `CouplingMetricRule` supports per-project configuration via `pyproject.toml`:

```toml
[tool.axm-audit.coupling]
fan_out_threshold = 12          # global threshold (default: 10)
orchestrator_bonus = 5          # extra allowance for orchestrator modules (default: 5)

[tool.axm-audit.coupling.overrides]
"cli" = 15                      # per-module override (matches by suffix)
"core.runner" = 18
```

**Orchestrator detection**: modules importing from ≥ 3 distinct sibling subpackages
are automatically classified as orchestrators and receive the `orchestrator_bonus`
on top of the base threshold. This avoids false positives on modules whose high
fan-out is structural (e.g. a `runner.py` that coordinates multiple subsystems).

## Existing rules as examples

| Rule | Pattern | Good example of |
|---|---|---|
| `LintingRule` | Subprocess + penalty | Parsing tool JSON output |
| `DocstringCoverageRule` | AST + ratio | Walking Python AST |
| `ComplexityRule` | API-first + subprocess fallback | Graceful degradation |
| `FileExistsRule` | Binary | Simplest possible rule |
| `CircularImportRule` | AST + graph algorithm | Complex analysis (Tarjan SCC) |
