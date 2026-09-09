# Troubleshooting

Common issues and their solutions when running `axm-audit`.

## Tool not found

**Symptom**: `FileNotFoundError` or `command not found` for tools like `ruff`, `mypy`, `bandit`.

**Note**: `axm-audit` requests several audit dependencies through `with_packages`. **mypy is an exception**: it must be available in the target environment, with its required stubs. Node tools also need project-local installation. Check the named tool and `uv` availability before retrying.

**Solution**: Ensure `uv` is installed and on your PATH:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or check tool availability:

```bash
axm audit . --json-output --category tooling
```

## Type check BLOCKED — incomplete environment

**Symptom**: `QUALITY_TYPE` fails with a message like
`Type check BLOCKED: audit environment incomplete — missing type stubs or unfollowed imports for: <lib>` (or
`mypy did not complete (exit code 2 …)`), instead of a `Type score: …/100` line.

**Cause**: the type audit refuses to report a green score when mypy could not
actually type-check the code. This happens when:

- a third-party library is imported but has **no type stubs** in the audited
  environment (`[import-untyped]`, `Library stubs not installed for "<lib>"`),
- a module is **truly missing** from the environment (`[import-not-found]`),
- mypy **aborted** before completing (exit code 2: blocking syntax/config
  error, or a 300-second timeout).

The result is deliberately a **loud failure, not a 100** — a silent pass would
mask the fact that the audited env is incomplete and the type result
unreliable. This is an **environment problem, not a code problem**.

**Solution**: fix the environment, then re-run the audit:

```bash
# install the missing stubs (the audit never installs them for you)
uv sync          # or: uv pip install types-<lib>
axm audit . --json-output --category type
```

The type rule does not request extra stubs. Prepare dependencies before
running it; ordinary `uv run` environment synchronization still applies.

## Timeout errors

**Symptom**: A check returns `returncode=124` or times out.

**Cause**: The shared Python runner defaults to 300 seconds; the pytest runner uses 900 seconds, and doc_gate defaults to 120. Individual rules can use other subprocess paths.

**Solutions**:

1. Filter to a specific category instead of running all checks:

    ```bash
    axm audit . --json-output --category lint
    ```

2. Use quick mode (lint + type only):

    ```python
    result = audit_project(Path("."), quick=True)
    ```

## pytest-cov fails

**Symptom**: `TestCoverageRule` fails with `No module named pytest` or coverage is 0%.

**Solutions**:

- Ensure `pytest` and `pytest-cov` are installed: `uv add --dev pytest pytest-cov`
- Check that your `pyproject.toml` has `[tool.pytest.ini_options]` configured
- Verify tests are discoverable: `uv run pytest --collect-only`

## Radon import error

**Symptom**: `ComplexityRule` falls back to subprocess mode.

**Cause**: `radon` is a declared runtime dependency; an import failure indicates an incomplete or broken installation. The rule tries `radon.complexity.cc_visit()` first, then falls back to `radon cc --json` as a subprocess.

**Solution**: Restore the declared runtime environment with `uv sync` (or reinstall `axm-audit`).

## Complexipy unavailable — cognitive layer disabled

**Symptom**: `ComplexityRule` returns `severity=WARNING` with message "cognitive layer disabled (complexipy unavailable)" and `details["cognitive_disabled"] == True`.

**Cause**: `complexipy` is required for the cognitive complexity layer (cognitive complexity > 15 is flagged). The rule tries `from complexipy import file_complexity` first, then falls back to a `complexipy` subprocess. Both unavailable means the rule degrades to CC-only (radon) mode and reports the degradation.

**Solution**: Install complexipy: `uv sync`. The implemented complexity thresholds are CC ≥ 11 or cognitive complexity > 15; project policy can be stricter.

## Score seems wrong

If the composite score doesn't match expectations:

1. Check individual category scores with `axm audit . --json-output`, or inspect the
   structured Python/MCP response.

2. Review the [scoring formula](../explanation/scoring.md) — each category has a different weight
3. A single scored category is normalized to 100. `quality_score` is `None` only when no numeric scored category remains.

## Green command with failed checks

The command exit code describes tool execution, not the quality verdict.
Read `failed` in audit JSON, `verdict` in test JSON and `count` in doc_gate
JSON. See [CLI contracts](../reference/cli.md).
