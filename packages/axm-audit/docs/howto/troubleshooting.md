# Troubleshooting

Common issues and their solutions when running `axm-audit`.

## Tool not found

**Symptom**: `FileNotFoundError` or `command not found` for tools like `ruff`, `mypy`, `bandit`.

**Note**: Since v0.5, `axm-audit` **auto-injects** its audit dependencies (ruff, mypy, bandit, pip-audit, deptry, pytest-cov) via `with_packages` — you **do not** need to install them in your project's environment. If you still see this error, it likely means `uv` itself is not available.

**Solution**: Ensure `uv` is installed and on your PATH:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or check tool availability:

```bash
axm-audit audit . --category tooling
```

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

## Complexipy unavailable — cognitive layer disabled

**Symptom**: `ComplexityRule` returns `severity=WARNING` with message "cognitive layer disabled (complexipy unavailable)" and `details["cognitive_disabled"] == True`.

**Cause**: `complexipy` is required for the cognitive complexity layer (Cog<15, SonarSource convention). The rule tries `from complexipy import file_complexity` first, then falls back to a `complexipy` subprocess. Both unavailable means the rule degrades to CC-only (radon) mode and reports the degradation.

**Solution**: Install complexipy: `uv add complexipy>=5.4.0`. The double constraint (CC<10 via ruff C901 + Cog<15 via axm-audit) is documented in your project CLAUDE.md.

## Score seems wrong

If the composite score doesn't match expectations:

1. Check individual category scores:

    ```bash
    axm-audit audit . --json | python -m json.tool
    ```

2. Review the [scoring formula](../explanation/scoring.md) — each category has a different weight
3. Remember that `quality_score` is `None` when only a single category is audited with `--category`
