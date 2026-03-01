# Troubleshooting

Common issues and their solutions when running `axm-audit`.

## Tool not found

**Symptom**: `FileNotFoundError` or `command not found` for tools like `ruff`, `mypy`, `bandit`.

**Solution**: Install the required tools in your project's virtual environment:

```bash
uv add --dev ruff mypy bandit radon pip-audit deptry
```

Or check tool availability first:

```bash
axm-audit audit . --category tooling
```

!!! tip
    `axm-audit` uses `run_in_project()` which detects your project's `.venv/` and runs tools via `uv run --directory`. Make sure tools are installed in the **project's** environment, not globally.

## Timeout errors

**Symptom**: A check returns `returncode=124` or times out.

**Cause**: All subprocess-based rules have a **300-second timeout**. Large projects or slow CI environments may hit this limit.

**Solutions**:

1. Filter to a specific category instead of running all checks:

    ```bash
    axm-audit audit . --category lint
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

**Cause**: `radon` is an optional dependency. The rule tries `radon.complexity.cc_visit()` first, then falls back to `radon cc --json` as a subprocess.

**Solution**: Install radon directly: `uv add --dev radon`

## Score seems wrong

If the composite score doesn't match expectations:

1. Check individual category scores:

    ```bash
    axm-audit audit . --json | python -m json.tool
    ```

2. Review the [scoring formula](../explanation/scoring.md) — each category has a different weight
3. Remember that `quality_score` is `None` when only a single category is audited with `--category`
