# Getting Started

This tutorial walks you through installing `axm-vault` and verifying your setup.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
uv add axm-vault
```

Or with pip:

```bash
pip install axm-vault
```

## Step 1: Verify Installation

```python
from axm_vault import __version__

print(f"axm-vault v{__version__}")
```

## Step 2: Declare a Credential Group

The catalog describes the credentials a package needs — schema only, no values:

```python
from axm_vault import CredentialGroup, CredentialSpec, Sensitivity

group = CredentialGroup(
    id="acme",
    package="axm-acme",
    title="Acme",
    specs=(
        CredentialSpec(name="api_key", env="ACME_API_KEY", kind="token"),
        CredentialSpec(
            name="region", env="ACME_REGION", kind="str",
            sensitivity=Sensitivity.CONFIG, required=False, default="eu",
        ),
    ),
)

print(group.spec("api_key").env)  # ACME_API_KEY
```

See the [Catalog Models reference](../reference/models.md) for every field.

## Step 3: Run the Tests

```bash
cd packages/axm-vault
make check
```

This runs lint + type check + security audit + tests.

## Next Steps

- [Catalog Models](../reference/models.md) — Full model reference
- [CLI Reference](../reference/cli.md) — Full command documentation
- [Architecture](../explanation/architecture.md) — How the project is structured
