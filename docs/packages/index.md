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

</div>

## Architecture

```mermaid
graph TD
    classDef ast fill:#092268,color:#ffffff,stroke:#1a3a8f
    classDef audit fill:#1a3a8f,color:#ffffff,stroke:#2a4a9f
    classDef init fill:#158DC4,color:#ffffff,stroke:#1a9dd4
    classDef git fill:#607D8B,color:#ffffff,stroke:#708D9B

    AST["axm-ast<br/><i>AST introspection</i>"]:::ast
    AUDIT["axm-audit<br/><i>Code auditing</i>"]:::audit --> AST
    INIT["axm-init<br/><i>Scaffolding</i>"]:::init
    GIT["axm-git<br/><i>Git automation</i>"]:::git
```
