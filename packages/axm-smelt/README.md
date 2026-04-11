<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-smelt — Deterministic token compaction for LLM inputs</strong>
</p>


<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-smelt/axm-audit.json" alt="axm-audit"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-smelt/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-smelt/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-smelt/"><img src="https://img.shields.io/pypi/v/axm-smelt" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io/smelt/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

`axm-smelt` reduces token consumption for LLM inputs by applying deterministic compaction strategies — lossless whitespace removal, structural transforms, and optional lossy simplifications. It works as a **CLI**, **Python API**, and **MCP tool** for AI agents.

📖 **[Full documentation](https://forge.axm-protocols.io/smelt/)**

## Features

- **Format detection** — auto-detect JSON, YAML, XML, TOML, CSV, Markdown, and plain text
- **Token counting** — exact counts via tiktoken (`o200k_base`), with `len//4` fallback
- **7 strategies** — `minify`, `drop_nulls`, `flatten`, `tabular`, `dedup_values`, `strip_quotes`, `round_numbers`
- **Composable pipeline** — chain strategies explicitly or use presets (`safe`, `moderate`, `aggressive`)
- **CLI** — `axm-smelt compact|check|count|version` with `--preset`/`--strategies`/`--file`/`--output` flags
- **MCP tool** — `SmeltTool` for use by AI agents via `axm-mcp`
- **Modern Python** — 3.12+ with strict typing

## Installation

```bash
uv add axm-smelt
```

## Quick Start

### CLI

```bash
# Compact from stdin (uses safe preset by default)
echo '{"name": "Alice", "age": 30}' | axm-smelt compact

# Compact a file with the aggressive preset
axm-smelt compact --file data.json --preset aggressive

# Compact with specific strategies, write output to file
axm-smelt compact --file data.json --strategies minify,drop_nulls --output out.json

# Analyze token waste without modifying (shows per-strategy estimates)
axm-smelt check --file data.json

# Count tokens
echo 'hello world' | axm-smelt count
```

### Python API

```python
from axm_smelt import smelt, check, count

# Compact using the safe preset (default)
report = smelt('{\n  "name": "Alice",\n  "age": 30\n}')
print(f"{report.savings_pct:.1f}% saved")
# Tokens: 14 -> 9

# Compact with explicit strategies
report = smelt(data, strategies=["minify", "drop_nulls"])

# Compact with a preset
report = smelt(data, preset="aggressive")

# Analyze without transforming
report = check('{"data": [1, 2, 3]}')
for strat, pct in report.strategy_estimates.items():
    print(f"  {strat}: {pct:.1f}%")

# Count tokens
tokens = count("hello world")
```

### MCP (AI Agent)

`axm-smelt` is available as an MCP tool via [`axm-mcp`](https://github.com/axm-protocols/axm-nexus/tree/main/packages/axm-mcp). AI agents can call `smelt_compact(data, preset="moderate")` directly.

See the [MCP how-to guide](https://forge.axm-protocols.io/smelt/howto/mcp/) for details.

## CLI Commands

| Command | Description |
|---|---|
| `axm-smelt compact` | Read from stdin/file, output compacted text; savings reported to stderr |
| `axm-smelt check` | Analyze token waste without transforming; shows strategies with positive savings |
| `axm-smelt count` | Print token count |
| `axm-smelt version` | Print version string |

All commands accept `--file PATH` to read from a file instead of stdin. `compact` additionally accepts `--strategies LIST`, `--preset NAME`, and `--output PATH`.

## Strategies

| Name | Category | Description |
|---|---|---|
| `minify` | whitespace | Lossless JSON whitespace compaction |
| `drop_nulls` | structural | Recursively remove `None`, `""`, `[]`, `{}` values |
| `flatten` | structural | Collapse single-child wrapper dicts (`{"a":{"b":1}}` → `{"a.b":1}`) |
| `tabular` | structural | Convert `list[dict]` JSON to pipe-separated tables |
| `dedup_values` | structural | Replace repeated long strings (≥20 chars, ≥2 occurrences) with aliases |
| `strip_quotes` | cosmetic | Remove quotes on simple alphanumeric JSON keys |
| `round_numbers` | cosmetic | Round floats to N decimal places (default: 2) |

## Presets

| Preset | Strategies | Use when |
|---|---|---|
| `safe` | `minify` | Lossless only — output is semantically identical |
| `moderate` | `minify`, `drop_nulls`, `flatten`, `dedup_values`, `tabular`, `strip_quotes` | Structural transforms are acceptable |
| `aggressive` | `minify`, `drop_nulls`, `flatten`, `tabular`, `round_numbers`, `dedup_values`, `strip_quotes` | Maximum savings, may alter float precision |

## Development

This package is part of the [**axm-forge**](https://github.com/axm-protocols/axm-forge) workspace.

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-groups
uv run --package axm-smelt --directory packages/axm-smelt pytest -x -q
```

## License

Apache-2.0 — © 2026 axm-protocols
