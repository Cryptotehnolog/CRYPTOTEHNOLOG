---
type: system
status: active
confidence: high
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
sources:
  - karpathy-llm-wiki-2026-04-04
  - project-review-2026-05-19
---

# Граф Базы Знаний

Эта страница содержит curated Mermaid-граф ключевых смысловых связей. Он не генерируется автоматически из всех Markdown-ссылок, потому что полный link graph быстро станет шумным.

Граф должен оставаться маленьким и показывать только важные связи:

- source -> concept,
- concept -> decision,
- decision -> risk,
- workflow -> automation script.

```mermaid
flowchart LR
    karpathy["Source: Karpathy LLM Wiki"]
    review["Source: Project Review"]
    deribit["Source: Deribit API"]
    hermesSource["Source: Hermes Agent"]
    omniSource["Source: OmniRoute"]
    polymarket["Source: Polymarket API"]
    quantum["Source: Quantum Bot"]

    llmWiki["Concept: LLM Wiki"]
    probabilityBasis["Concept: Probability Basis"]

    firstMvp["Decision: First MVP"]
    probabilityStrategy["Strategy: Probability Basis"]
    fundingStrategy["Strategy: Funding Carry"]
    ivSpec["Spec: Deribit IV Calculation"]

    automationRisk["Risk: Automation Quality"]
    settlementRisk["Risk: Settlement / Definition Mismatch"]
    probabilityRisk["Risk: Probability Basis"]

    dataPipeline["Architecture: Data Pipeline"]
    replay["Architecture: Deterministic Replay"]
    postgresSchema["Schema: PostgreSQL Tables"]
    rustContracts["Contracts: Rust Events"]
    configDocs["Docs: Config Parameters"]
    roadmap["Roadmap: MVP"]

    codexWorkflow["Workflow: Codex Wiki Usage"]
    obsidianWorkflow["Workflow: Obsidian"]
    healthWorkflow["Workflow: Wiki Health Check"]
    ingestWorkflow["Workflow: Source Ingestion"]
    codingStandards["Workflow: Coding Standards"]
    agentResearch["Workflow: Agent Research"]
    researchVsCore["Workflow: Research Vs Core"]

    hermesTool["Tool: Hermes Agent"]
    omniTool["Tool: OmniRoute"]

    kbCheck["Script: kb_health_check.ps1"]
    linkCheck["Script: validate_local_links.ps1"]
    checkAll["Script: check_all.ps1"]
    sourceNote["Script: new_source_note.ps1"]
    hooks["Script: install_hooks.ps1"]
    compliance["Script: check_compliance.ps1"]

    karpathy --> llmWiki
    karpathy --> codexWorkflow
    karpathy --> ingestWorkflow
    deribit --> probabilityBasis
    hermesSource --> hermesTool
    omniSource --> omniTool
    polymarket --> probabilityBasis
    quantum -.-> probabilityBasis
    review --> probabilityBasis
    review --> fundingStrategy
    probabilityBasis --> firstMvp
    probabilityBasis --> probabilityStrategy
    probabilityStrategy --> ivSpec
    probabilityStrategy --> probabilityRisk
    firstMvp --> automationRisk
    firstMvp --> settlementRisk
    firstMvp --> roadmap
    dataPipeline --> replay
    dataPipeline --> postgresSchema
    dataPipeline --> rustContracts
    dataPipeline --> configDocs
    replay --> roadmap

    codexWorkflow --> kbCheck
    obsidianWorkflow --> kbCheck
    healthWorkflow --> kbCheck
    healthWorkflow --> linkCheck
    ingestWorkflow --> sourceNote
    codingStandards --> compliance
    hermesTool --> agentResearch
    omniTool --> agentResearch
    agentResearch --> roadmap
    agentResearch --> researchVsCore
    probabilityStrategy --> researchVsCore
    kbCheck --> hooks
    linkCheck --> checkAll
    compliance --> checkAll
```

## Правило Поддержки

Codex обновляет этот граф только при появлении важных новых связей. Не нужно добавлять сюда каждую Markdown-ссылку.

При добавлении новой `decision` или `risk` страницы Codex обязан явно проверить, нужно ли добавить ее в этот граф. Если важной смысловой связи нет, граф можно не менять, но это решение должно быть осознанным.
