# Use via MCP

Integrate `axm-audit` into AI agent workflows through the AXM MCP server.

## Setup

The `axm-audit` tool is exposed as `audit` by the `axm-mcp` server. No separate installation needed — if `axm-mcp` is running, the audit tool is available.

## Usage

### From an AI agent

Call the `audit` MCP tool with the project path:

```json
{"tool": "audit", "kwargs": {"path": "/path/to/project"}}
```

The output uses `format_agent` — compact strings for clean passes, detailed dicts for actionable items. For failed checks, `text` and `details` are mutually exclusive — `text` takes priority when truthy, otherwise `details` is included:

```json
{
  "score": 85.0,
  "grade": "B",
  "passed": ["QUALITY_LINT: Lint score: 100/100 (0 issues)"],
  "failed": [{"rule_id": "...", "details": {...}, "fix_hint": "..."}]
}
```

### One-shot verification

Use `verify` instead of `audit` for a combined quality + governance check:

```json
{"tool": "verify", "kwargs": {"path": "/path/to/project"}}
```

This runs `audit` + `init_check` + AST enrichment in a single call.

### Agent-optimized test runner

Use `audit_test` for structured, token-efficient test feedback:

```json
{"tool": "audit_test", "kwargs": {"path": "/path/to/project", "mode": "failures"}}
```

| Mode | ~Tokens | Use case |
|---|---|---|
| `compact` | 30 | Fast-feedback loops (pass/fail + counts) |
| `failures` | 30-200 | First run, debugging (includes failure details) |
| `delta` | 100-300 | Post-refactor coverage comparison |
| `targeted` | 50-150 | Impact-scoped tests with `files` or `markers` |

## Output Format

The MCP tool returns the same structure as `axm-audit audit . --agent`:

| Key | Type | Content |
|---|---|---|
| `score` | `float` | Composite quality score (0–100) |
| `grade` | `str` | Letter grade A–F |
| `passed` | `list` | Strings or dicts with actionable details |
| `failed` | `list` | Dicts with `rule_id`, `message`, `details`, `fix_hint` |

For scoring details, see [Scoring & Grades](../explanation/scoring.md).
