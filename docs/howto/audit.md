# Audit Your Project

Run a full quality audit on your Python project.

## Steps

```bash
axm-init audit
```

The audit checks your project against AXM governance standards and assigns a grade from **A** (excellent) to **F** (failing).

## What gets checked

| Category | Checks |
|---|---|
| Structure | `src/` layout, `pyproject.toml`, `tests/` directory |
| Tooling | Ruff, MyPy, Pytest configuration |
| CI/CD | GitHub Actions workflows |
| Security | `pip-audit` in dev deps |
| Documentation | MkDocs setup, README |
