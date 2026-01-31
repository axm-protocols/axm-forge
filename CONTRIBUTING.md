# Contributing to AXM

## Development Setup

```bash
git clone https://github.com/axm-protocols/axm.git
cd axm
make install
```

## Commands

```bash
make check      # Lint + audit + tests
make format     # Auto-format code
make docs-serve # Local docs preview
```

## Standards

- Python 3.12+ with type hints
- Google-style docstrings
- TDD approach

## Pull Request

1. Write tests first
2. Run `make check`
3. Update CHANGELOG.md if user-facing
