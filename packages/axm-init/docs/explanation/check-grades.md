# Understanding Check Grades

## Overview

`axm init_check` scores your project against the AXM gold standard — checks derived from the best practices embedded in the project template and CI configurations. A **paper** (an `[tool.axm-lab]` project) is not a Python distribution and is graded on its own invariants instead: see [paper checks](../reference/checks/catalogue.md#paper-15-pts).

## Grade Scale

| Grade | Score Range | Meaning |
|-------|-----------|---------|
| **A** 🏆 | 90–100 | Meets at least 90% of selected weighted checks |
| **B** ✅ | 75–89 | Good — minor improvements needed |
| **C** ⚠️ | 60–74 | Acceptable — several gaps |
| **D** 🔧 | 40–59 | Below standard — significant work needed |
| **F** ❌ | 0–39 | Failing — major structural issues |

## Scoring System

Each check has a **weight** (1–5 points). The score is computed over the checks
that **actually run** for the project's context, not against a fixed point total:

```
Score = round(earned points / weight of executed checks × 100)
```

The denominator is **dynamic**. The check engine selects which checks run from the
project context (standalone, workspace, member, paper, experiment). A workspace
selects workspace checks and skips package-only checks. For members, some checks
are skipped while CI and shared tooling checks are redirected to the workspace
root. A paper runs its three paper invariants; an experiment runs its two form
invariants. See [project contexts](project-contexts.md).

If no weighted check applies, the result is N/A: structured score and grade
are null and the CLI exits successfully. Otherwise the score is normalized to
0–100 and mapped to the grade boundaries above.

## Check catalogue

The [Python catalogue](../reference/checks/catalogue.md) lists each check and
weight, plus the framework-specific category sets. Scores are based on the
selected checks, not on the size of that catalogue.

## Improving Your Score

Every failed check includes a **Fix** instruction telling you exactly what to do. Run `axm init_check` iteratively until you reach Grade A.

!!! tip "Quick win"
    Scaffolds aim at the configured standard; measure the actual result after
    installing dependencies and hooks. Grade A is not the CLI success threshold:
    an applicable run exits successfully only at **100/100**.
