---
type: risk
status: active
confidence: high
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
sources:
  - karpathy-llm-wiki-2026-04-04
---

# Риск: Качество Автоматизации

Полностью автоматическое обслуживание wiki может создать ложное чувство уверенности, если generated summaries воспринимать как факты.

## Failure Modes

- LLM объединяет разные concepts под одним названием.
- Появляются duplicate pages для одного concept.
- Слабый inference превращается в уверенное project claim.
- Старые claims остаются после того, как новые sources им противоречат.
- Важные rejections исчезают, потому что индексируются только active decisions.

## Mitigation

- Держать raw source notes immutable.
- Требовать frontmatter с `confidence` и `status`.
- Индексировать rejected и superseded pages.
- Явно сохранять contradictions.
- Запускать health checks после каждого ingest.
- Считать wiki project memory, а не runtime truth для trading.
