---
hide:
  - toc
---

# Packages

<div class="grid cards" markdown>

-   :material-file-tree:{ .lg .middle } **axm-ast**

    ---

    AST introspection CLI for AI agents, powered by tree-sitter.

    [:octicons-arrow-right-24: Getting Started](../ast/)

-   :material-shield-check:{ .lg .middle } **axm-audit**

    ---

    Code auditing and quality rules for Python projects.

    [:octicons-arrow-right-24: Getting Started](../audit/)

-   :material-cube-outline:{ .lg .middle } **axm-init**

    ---

    Python project scaffolding CLI with Copier templates.

    [:octicons-arrow-right-24: Getting Started](../init/)

-   :material-source-branch:{ .lg .middle } **axm-git**

    ---

    Git workflow automation for AXM agents.

    [:octicons-arrow-right-24: Getting Started](../git/)

-   :material-compress:{ .lg .middle } **axm-smelt**

    ---

    Deterministic token compaction for LLM inputs.

    [:octicons-arrow-right-24: Getting Started](../smelt/)

</div>

## Architecture

```mermaid
graph TD
    classDef ast fill:#5C6BC0,stroke:#3949AB
    classDef audit fill:#42A5F5,stroke:#1E88E5
    classDef init fill:#26C6DA,stroke:#00ACC1
    classDef git fill:#78909C,stroke:#546E7A
    classDef smelt fill:#FFA726,stroke:#FB8C00

    AST["axm-ast\nAST introspection"]:::ast
    AUDIT["axm-audit\nCode auditing"]:::audit --> AST
    INIT["axm-init\nScaffolding"]:::init
    GIT["axm-git\nGit automation"]:::git
    SMELT["axm-smelt\nToken compaction"]:::smelt
```
