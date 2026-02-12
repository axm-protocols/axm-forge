# axm-audit

<p align="center">
  <a href="https://github.com/JarryGabriel/axm-audit/actions/workflows/ci.yml"><img src="https://github.com/JarryGabriel/axm-audit/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://coveralls.io/github/JarryGabriel/axm-audit?branch=main"><img src="https://coveralls.io/repos/github/JarryGabriel/axm-audit/badge.svg?branch=main" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-audit/"><img src="https://img.shields.io/pypi/v/axm-audit" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/typed-strict-blue" alt="Typed">
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
  <a href="https://github.com/astral-sh/uv"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="uv"></a>
  <a href="https://JarryGabriel.github.io/axm-audit/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

> Code auditing and quality rules for AXM — 5-layer analysis with composite scoring.

## Features

- **5-layer analysis** — structure, quality (lint + type + complexity), architecture, security, practices
- **Composite scoring** — weighted formula producing a 0–100 score with letter grade (A–F)
- **Category filtering** — audit only `structure`, `quality`, `architecture`, or `practice`
- **Multiple reporters** — JSON for agents, Markdown for humans
- **Python API** — `audit_project()` returns typed `AuditResult` Pydantic models

## Installation

```bash
uv add axm-audit
```

## Quick Start

```python
from axm_audit import audit_project
from pathlib import Path

result = audit_project(Path("."))
print(f"Score: {result.quality_score}/100 — Grade {result.grade}")
```

## Development

```bash
git clone https://github.com/JarryGabriel/axm-audit.git
cd axm-audit
make install
make check
```

## License

MIT - See [LICENSE](LICENSE) for details.
