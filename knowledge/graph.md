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
    polymarket["Source: Polymarket API"]
    quantum["Source: Quantum Bot"]

    llmWiki["Concept: LLM Wiki"]
    probabilityBasis["Concept: Probability Basis"]

    firstMvp["Decision: First MVP"]
    probabilityStrategy["Strategy: Probability Basis"]
    fundingStrategy["Strategy: Funding Carry"]

    automationRisk["Risk: Automation Quality"]
    settlementRisk["Risk: Settlement / Definition Mismatch"]
    probabilityRisk["Risk: Probability Basis"]

    dataPipeline["Architecture: Data Pipeline"]
    replay["Architecture: Deterministic Replay"]
    roadmap["Roadmap: MVP"]

    codexWorkflow["Workflow: Codex Wiki Usage"]
    obsidianWorkflow["Workflow: Obsidian"]
    healthWorkflow["Workflow: Wiki Health Check"]
    ingestWorkflow["Workflow: Source Ingestion"]

    kbCheck["Script: kb_health_check.ps1"]
    linkCheck["Script: validate_local_links.ps1"]
    checkAll["Script: check_all.ps1"]
    sourceNote["Script: new_source_note.ps1"]
    hooks["Script: install_hooks.ps1"]

    karpathy --> llmWiki
    karpathy --> codexWorkflow
    karpathy --> ingestWorkflow
    deribit --> probabilityBasis
    polymarket --> probabilityBasis
    quantum -.-> probabilityBasis
    review --> probabilityBasis
    review --> fundingStrategy
    probabilityBasis --> firstMvp
    probabilityBasis --> probabilityStrategy
    probabilityStrategy --> probabilityRisk
    firstMvp --> automationRisk
    firstMvp --> settlementRisk
    firstMvp --> roadmap
    dataPipeline --> replay
    replay --> roadmap

    codexWorkflow --> kbCheck
    obsidianWorkflow --> kbCheck
    healthWorkflow --> kbCheck
    healthWorkflow --> linkCheck
    ingestWorkflow --> sourceNote
    kbCheck --> hooks
    linkCheck --> checkAll
```

## Правило Поддержки

Codex обновляет этот граф только при появлении важных новых связей. Не нужно добавлять сюда каждую Markdown-ссылку.

При добавлении новой `decision` или `risk` страницы Codex обязан явно проверить, нужно ли добавить ее в этот граф. Если важной смысловой связи нет, граф можно не менять, но это решение должно быть осознанным.
