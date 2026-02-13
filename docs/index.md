---
hide:
  - navigation
  - toc
---

# axm-mcp

<p align="center">
  <strong>MCP server for the AXM protocol ecosystem.</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-mcp/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-mcp/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://axm-protocols.github.io/axm-mcp/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-mcp/gh-pages/badges/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-mcp/actions/workflows/axm-audit.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-mcp/gh-pages/badges/axm-audit.json" alt="axm-audit"></a>
  <a href="https://coveralls.io/github/axm-protocols/axm-mcp?branch=main"><img src="https://coveralls.io/repos/github/axm-protocols/axm-mcp/badge.svg?branch=main" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-mcp/"><img src="https://img.shields.io/pypi/v/axm-mcp" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://axm-protocols.github.io/axm-mcp/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

## What is axm-mcp?

`axm-mcp` is the Model Context Protocol (MCP) server that bridges AXM tools to AI agents. It auto-discovers all `axm.tools` entry points from installed packages and exposes them as MCP-callable tools — no configuration needed.

## How it Works

```mermaid
graph LR
    Agent["AI Agent"] --> MCP["axm-mcp"]
    MCP --> Discover["discover_tools()"]
    Discover --> EP1["axm.tools: ast_describe"]
    Discover --> EP2["axm.tools: audit"]
    Discover --> EP3["axm.tools: init_check"]
    Discover --> EPN["axm.tools: ..."]
    MCP --> Verify["verify()"]
    Verify --> EP2
    Verify --> EP3
    Verify --> EP1
```

## Features

- 🔌 **Auto-discovery** — Finds all `axm.tools` entry points at startup
- 🛠️ **MCP bridge** — Each tool becomes an MCP-callable function
- ✅ **Verify** — Built-in meta-tool: audit + init check + AST enrichment in one call
- 📋 **List tools** — Built-in meta-tool to inspect all available tools

## Quick Example

```bash
# Start the MCP server
axm-mcp
```

All installed AXM tools are immediately available to any MCP client.

---

<div style="text-align: center; margin: 2rem 0;">
  <a href="tutorials/quickstart/" class="md-button md-button--primary">Get Started →</a>
  <a href="reference/cli/" class="md-button">CLI Reference</a>
</div>
