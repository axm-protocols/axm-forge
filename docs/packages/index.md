---
hide:
  - toc
---

# Packages

<div class="grid cards" markdown>

-   :material-package-variant-closed:{ .lg .middle } **axm**

    ---

    AXM CLI — thin autodiscovery wrapper for the ecosystem.

    [:octicons-arrow-right-24: Getting Started](../axm/index.md)

-   :octicons-server-16:{ .lg .middle } **axm-mcp**

    ---

    MCP Server — runtime tool discovery and execution.

    [:octicons-arrow-right-24: Getting Started](../mcp/index.md)

-   :material-file-tree:{ .lg .middle } **axm-ast**

    ---

    AST introspection CLI for AI agents, powered by tree-sitter.

    [:octicons-arrow-right-24: Getting Started](../ast/index.md)

-   :material-shield-check:{ .lg .middle } **axm-audit**

    ---

    Code auditing and quality rules for Python projects.

    [:octicons-arrow-right-24: Getting Started](../audit/index.md)

-   :material-cube-outline:{ .lg .middle } **axm-init**

    ---

    Python project scaffolding CLI with Copier templates.

    [:octicons-arrow-right-24: Getting Started](../init/index.md)

-   :material-source-branch:{ .lg .middle } **axm-git**

    ---

    Git workflow automation for AXM agents.

    [:octicons-arrow-right-24: Getting Started](../git/index.md)

-   :material-arrow-collapse-vertical:{ .lg .middle } **axm-smelt**

    ---

    Deterministic token compaction for LLM inputs.

    [:octicons-arrow-right-24: Getting Started](../smelt/index.md)

-   :material-package-variant-closed:{ .lg .middle } **axm-ingot**

    ---

    Shared helper library — common code factored out and tested once, reused across packages.

    [:octicons-arrow-right-24: Getting Started](../ingot/index.md)

</div>

## Architecture

```mermaid
%%{ init: { "flowchart": { "defaultRenderer": "elk" } } }%%
graph TD
    classDef ast fill:#5C6BC0,stroke:#3949AB,color:#fff
    classDef audit fill:#42A5F5,stroke:#1E88E5,color:#fff
    classDef init fill:#26C6DA,stroke:#00ACC1,color:#fff
    classDef git fill:#78909C,stroke:#546E7A,color:#fff
    classDef smelt fill:#FFA726,stroke:#FB8C00,color:#fff
    classDef anvil fill:#EF5350,stroke:#E53935,color:#fff
    classDef edit fill:#AB47BC,stroke:#8E24AA,color:#fff
    classDef axm fill:#66BB6A,stroke:#43A047,color:#fff
    classDef mcp fill:#8D6E63,stroke:#6D4C41,color:#fff
    classDef ingot fill:#BDBDBD,stroke:#757575,color:#000

    subgraph tools [Tools]
        direction TB

        AUDIT["axm-audit<br/>Code auditing"]:::audit
        ANVIL["axm-anvil<br/>CST refactoring"]:::anvil

        subgraph botrow [ ]
            direction LR
            AST["axm-ast<br/>AST introspection"]:::ast
            EDIT["axm-edit<br/>Batch file editing"]:::edit
            INIT["axm-init<br/>Scaffolding"]:::init
            GIT["axm-git<br/>Git automation"]:::git
            SMELT["axm-smelt<br/>Token compaction"]:::smelt
        end

        AUDIT --> AST
        AUDIT --> ANVIL
        ANVIL --> EDIT
    end

    subgraph foundations [Foundations]
        direction TB
        subgraph baserow [ ]
            direction LR
            MCP["axm-mcp<br/>MCP Server"]:::mcp
            AXM["axm<br/>Core SDK + ToolResult"]:::axm
            INGOT["axm-ingot<br/>Shared helper library"]:::ingot
        end
    end

    %% the whole tool layer builds on the shared foundations
    %% (target a node inside baserow so ELK fills + aligns that row)
    tools --> AXM

    %% hide the inner row containers (keep only Tools / Foundations frames)
    style botrow fill:none,stroke:none
    style baserow fill:none,stroke:none
```
