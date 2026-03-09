# axm-forge

> 🔧 AXM Forge workspace — Dev tools for AI agents: AST introspection, quality gates, scaffolding, git automation.

## Packages

| Package | Description |
|---|---|
| [axm-ast](packages/axm-ast/) | AST introspection powered by tree-sitter |
| [axm-audit](packages/axm-audit/) | Code auditing, quality rules, and test runner |
| [axm-init](packages/axm-init/) | Project scaffolding and governance checks |
| [axm-git](packages/axm-git/) | Git workflow automation (commit, branch, tag, push) |

## Development

```bash
# Install all dependencies
uv sync --all-groups

# Run all tests
make test-all

# Lint + type-check
make lint

# Full CI pipeline
make ci
```

## License

Apache-2.0
