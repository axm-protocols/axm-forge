# CLI Reference

## Commands

### `axm-smelt compact`

Compact input and print the result.

```
axm-smelt compact [--file PATH] [--strategies LIST] [--preset NAME] [--output PATH]
```

| Flag | Default | Description |
|---|---|---|
| `--file PATH` | stdin | Read from file instead of stdin |
| `--strategies LIST` | — | Comma-separated strategy names |
| `--preset NAME` | `safe` | Named preset (`safe`, `moderate`, `aggressive`) |
| `--output PATH` | stdout | Write compacted text to file |

Compacted text goes to stdout (or `--output`). Savings summary goes to stderr.

Exits with code 1 on unknown preset, unknown strategy, or missing file.

### `axm-smelt check`

Analyze input without transforming it. Shows per-strategy savings estimates.

```
axm-smelt check [--file PATH]
```

| Flag | Default | Description |
|---|---|---|
| `--file PATH` | stdin | Read from file instead of stdin |

### `axm-smelt count`

Count tokens in input.

```
axm-smelt count [--file PATH] [--model MODEL]
```

| Flag | Default | Description |
|---|---|---|
| `--file PATH` | stdin | Read from file instead of stdin |
| `--model MODEL` | `o200k_base` | tiktoken encoding name |

### `axm-smelt version`

Print the version string.

```
axm-smelt version
```

## Python API

Auto-generated API reference is available under [Python API](api/).
