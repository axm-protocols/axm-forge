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

`axm-smelt` reduces token consumption for LLM inputs by applying deterministic compaction strategies. It detects the input format, runs the selected strategies in pipeline order, and reports exact token savings via tiktoken.

| Strategy | Category | Effect |
|---|---|---|
| `minify` | whitespace | Remove whitespace from JSON |
| `drop_nulls` | structural | Remove `None`, `""`, `[]`, `{}` values |
| `flatten` | structural | Collapse single-child wrapper dicts |
| `tabular` | structural | Convert `list[dict]` to pipe-separated tables |
| `dedup_values` | structural | Replace repeated long strings with aliases |
| `strip_quotes` | cosmetic | Remove quotes on simple JSON keys |
| `round_numbers` | cosmetic | Round floats to N decimal places |

## Quick Example

```bash
# CLI
echo '{"name": "Alice", "age": 30}' | axm-smelt compact

# Or use a preset
axm-smelt compact --file data.json --preset aggressive
```

```python
# Python API
from axm_smelt import smelt, check, count

report = smelt('{\n  "name": "Alice",\n  "age": 30\n}')
print(f"{report.savings_pct:.1f}% saved")
# 35.7% saved
```

## Features

- **Format detection** — auto-detect JSON, YAML, XML, TOML, CSV, Markdown, and plain text
- **Token counting** — exact counts via tiktoken (`o200k_base`), with `len//4` fallback
- **Composable pipeline** — chain strategies or use presets (`safe`, `moderate`, `aggressive`)
- **CLI** — `axm-smelt compact|check|count|version` commands
- **MCP tool** — available to AI agents via `axm-mcp`
- **Modern Python** — 3.12+ with strict typing

## Learn More

- [Getting Started Tutorial](tutorials/getting-started.md)
- [Compact Data](howto/compact.md)
- [Use Strategies](howto/strategies.md)
- [Use Presets](howto/presets.md)
- [Analyze Token Waste](howto/check.md)
- [Use via MCP](howto/mcp.md)
- [Strategy Catalog](explanation/strategies.md)
- [Format Detection](explanation/formats.md)
