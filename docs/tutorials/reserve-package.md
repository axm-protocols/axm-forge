# Reserve a Package Name on PyPI

> **Goal:** Claim your package name on PyPI before you're ready to publish
> **Time:** 3 minutes
> **Prerequisites:** PyPI account with API token

## Overview

Ever found the perfect package name, only to discover it's taken when you're ready to publish? AXM's `reserve` command lets you claim a name on PyPI immediately with a minimal placeholder package.

## Step 1: Get Your PyPI API Token

1. Log in to [pypi.org](https://pypi.org)
2. Go to **Account Settings** → **API tokens**
3. Create a new token with **Entire account** scope
4. Copy the token (starts with `pypi-`)

## Step 2: Set Up Your Token

Option A — Environment variable (recommended for CI):

```bash
export PYPI_API_TOKEN=pypi-YOUR_TOKEN_HERE
```

Option B — Interactive prompt (AXM will ask and optionally save to `~/.pypirc`).

## Step 3: Check Name Availability (Dry Run)

Before reserving, test with `--dry-run`:

```bash
axm reserve my-awesome-package --dry-run
```

Expected output:

```
✅ Package 'my-awesome-package' is available
✅ Dry run: Would publish placeholder to PyPI
```

If the name is taken:

```
❌ Package 'my-awesome-package' is already taken on PyPI
```

## Step 4: Reserve the Name

When ready, run without `--dry-run`:

```bash
axm reserve my-awesome-package
```

Expected output:

```
✅ Package 'my-awesome-package' reserved on PyPI (v0.0.1)
   View at: https://pypi.org/project/my-awesome-package/
```

## Step 5: Verify on PyPI

Visit the URL shown in the output. You'll see a placeholder package with:

- Version `0.0.1`
- Description: "Package name reserved"
- Your author information

## Command Options

```bash
axm reserve NAME [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--author, -a` | Author name (default: from git config) |
| `--email, -e` | Author email (default: from git config) |
| `--dry-run` | Check availability without publishing |
| `--json` | Output as JSON (for CI) |

## JSON Output for CI

```bash
axm reserve my-package --json
```

```json
{
  "success": true,
  "package_name": "my-package",
  "version": "0.0.1",
  "message": "Package 'my-package' reserved on PyPI"
}
```

## Best Practices

1. **Reserve early** — Good names go fast
2. **Use consistent naming** — Match your GitHub repo name
3. **Add real content soon** — Don't leave placeholders indefinitely
4. **Avoid typosquatting** — Only reserve names you intend to use

## What's Next?

- [CLI Reference](../reference/cli.md) — Full command documentation
- [Understanding Audit Grades](./audit-grades.md) — Improve your project quality
