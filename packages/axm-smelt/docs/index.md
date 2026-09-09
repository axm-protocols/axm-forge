<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="140" />
</p>

<h1 align="center">axm-smelt</h1>
<p align="center"><strong>Deterministic token compaction for LLM inputs.</strong></p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-smelt/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-smelt/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-smelt/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-smelt/"><img src="https://img.shields.io/pypi/v/axm-smelt" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" />
</p>

---

## What it does

`axm-smelt` reduces token consumption through deterministic transformations.
It detects formats, tries selected strategies and keeps only candidates with
fewer tokens, or equal tokens and fewer characters. No LLM summarization is used.

Use the Python API or the three registered AXMTools: `smelt`, `smelt_check`,
and `smelt_count`. The registry provides AXM CLI, MCP and DAG access.

## Quick example

```python
import json
from axm_smelt import smelt

report = smelt('{\n  "name": "Alice",\n  "age": 30\n}')
assert json.loads(report.compacted) == {"name": "Alice", "age": 30}
print(report.compacted, report.savings_pct)
```

A token reduction does not prove that meaning is preserved. The default
`safe` preset can alter XML whitespace, YAML inline comments and Markdown
layout. Structural presets can change schema or produce text that is not JSON.
Read [strategy behavior](explanation/strategies.md) before choosing a preset.

## Find your way

| Your question | Start here |
|---|---|
| How do I make my first verified compaction? | [Getting Started](tutorials/getting-started.md) |
| How do I compact, save or analyze a payload? | [How-to guides](howto/index.md) |
| What do functions, reports and tools accept/return? | [Contracts](reference/contracts.md) |
| How do I encode command-line arguments? | [CLI reference](reference/cli.md) |
| Where is the supported Python API? | [Public API](reference/api/index.md) |
| Why was a candidate accepted or skipped? | [Architecture](explanation/architecture.md) |
| How are inputs classified? | [Format detection](explanation/formats.md) |

JSON, YAML, XML, TOML, CSV, Markdown and text are detected. Detection is broader
than compaction support: TOML/CSV have no dedicated compactor.
Token counts use tiktoken; Claude/unknown names resolve to an approximate
`o200k_base` proxy in the counting API.
