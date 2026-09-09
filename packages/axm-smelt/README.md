<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-smelt — Deterministic token compaction for LLM inputs</strong>
</p>


<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-smelt/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-smelt/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-smelt/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-smelt/"><img src="https://img.shields.io/pypi/v/axm-smelt" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io/smelt/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

`axm-smelt` reduces token consumption for LLM inputs with deterministic
transformations. It detects input formats, tries ordered strategies, and keeps
candidates that reduce tokens or shorten text at equal token count.

**[Full documentation](https://forge.axm-protocols.io/smelt/)** ·
[Getting started](docs/tutorials/getting-started.md) ·
[Python/tool contracts](docs/reference/contracts.md)

## Installation

Requires Python 3.12+. In a uv project:

```bash
uv add axm-smelt
```

## Quick start

```python
import json
from axm_smelt import check, count, smelt

data = '{\n  "name": "Alice",\n  "age": 30\n}'
report = smelt(data)
assert json.loads(report.compacted) == json.loads(data)
print(report.compacted, report.savings_pct)

analysis = check(data)
print(analysis.strategy_estimates)  # Independent estimates; do not add them
assert analysis.savings_pct == report.savings_pct
print(count("hello world"))
```

The Python surface also exports `SmeltReport`, `Format`, `CounterBackend`
and `__version__`. Compaction returns new text; it does not overwrite a file.

## AXM tools and CLI

Three `axm.tools` registrations supply CLI, MCP and DAG access:

| Command | Result |
|---|---|
| `axm smelt` | Compacted text and pipeline metrics |
| `axm smelt_check` | Input format/count and isolated strategy estimates |
| `axm smelt_count` | Token count with a requested model/encoding |

```bash
printf '{"name": "Alice", "notes": null}\n' | uv run axm smelt --json-output
uv run axm smelt --data '{"a": 1, "b": null}' --strategies '["minify", "drop_nulls"]'
uv run axm smelt_count --data 'hello world' --model o200k_base
```

Use `--input-path ./payload.json` to read a UTF-8 file. Nonempty data takes
precedence over the file, then non-interactive stdin. JSON-looking `--data`
is decoded by the CLI; use a file/stdin to preserve its original whitespace
baseline. Plain stdout includes a header; `--json-output` prints the data
mapping. See [CLI reference](docs/reference/cli.md) for errors and encoding.

For MCP, install the package into the server environment and call
`axm_call(name="smelt", arguments={...})` in façade mode.
[Integration guide](docs/howto/mcp.md).

## Strategies and fidelity

| Preset | Intent |
|---|---|
| `safe` (default) | `minify` and `collapse_whitespace` |
| `moderate` | Also drop empties, flatten, alias repeated strings, tabularize, remove quotes/comments |
| `aggressive` | Also round floats; order differs from moderate |

The name `safe` is **not a general losslessness guarantee**. XML significant
whitespace, YAML inline comments and Markdown layout can change. Structural
transforms can lose values/types and produce output that is not valid JSON.
Inspect [strategy behavior and limits](docs/explanation/strategies.md) before
choosing a preset. More strategies do not guarantee greater savings.

Detected formats: JSON, YAML, XML, TOML, CSV, Markdown and text. TOML/CSV have
no dedicated compactor. Counts use tiktoken; Claude and unknown model names
use an `o200k_base` proxy, not the target model's exact tokenizer or billing.
The `smelt`/`check` pipelines always use `o200k_base`.

## Development

This package belongs to the [axm-forge workspace](https://github.com/axm-protocols/axm-forge).

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-groups
uv run --package axm-smelt --directory packages/axm-smelt pytest -x -q
```

## License

Apache-2.0 — © 2026 axm-protocols
