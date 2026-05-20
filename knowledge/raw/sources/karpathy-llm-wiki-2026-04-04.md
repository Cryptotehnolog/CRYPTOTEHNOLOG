---
type: source
status: active
confidence: high
stability: stable
updated: 2026-05-20
review_after: null
source_id: karpathy-llm-wiki-2026-04-04
title: LLM Wiki
author: Andrej Karpathy
created: 2026-04-04
url: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
---

# Source Note: Karpathy LLM Wiki

## Summary

Karpathy описывает паттерн построения личных или проектных баз знаний с помощью LLM agents. Ключевая идея - не доставать raw chunks из документов заново на каждый query, а постепенно строить и поддерживать persistent Markdown wiki между пользователем и raw sources.

Raw sources остаются immutable. Wiki генерируется и поддерживается LLM. Schema file объясняет LLM, как структурировать pages, ingest new sources, отвечать на вопросы, обновлять index, поддерживать log и периодически lint wiki.

## Key Takeaways Для CRYPTOTEHNOLOG

- Использовать raw source notes как immutable evidence.
- Поддерживать synthesized wiki как project memory layer.
- Держать `index.md` как content map.
- Держать `log.md` как chronological audit trail.
- Разрешить Codex routine maintenance: summaries, links, filing, contradiction notes и health checks.
- Не путать generated synthesis с source truth.

## Engineering Interpretation

Проект должен использовать LLM Wiki pattern для architecture decisions, strategy research, market API notes, risk assumptions и post-trade analysis. Он не должен использовать wiki как execution-time dependency для deterministic trading core.

## Source Handling

Эта note пересказывает source и ссылается на original gist. Она намеренно не копирует полный source text.
