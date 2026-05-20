---
type: source
status: active
confidence: medium
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
source_id: hermes-agent-2026-05-20
title: Hermes Agent Documentation
author: Hermes Agent / Nous Research ecosystem
created: 2026-05-20
url: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/mcp.md
---

# Source Note: Hermes Agent

## Summary

Hermes Agent рассматривается как future research-layer agent runtime для CRYPTOTEHNOLOG.

Ключевая полезность для проекта:

- подключение external tools через MCP,
- долгоживущая project/research memory,
- запуск исследовательских workflows,
- генерация hypotheses на основе накопленных post-trade и replay data.

## Project Impact

Hermes может стать orchestration layer для research agents, но не должен становиться частью deterministic trading core.

Разрешенный scope:

- анализ historical observations,
- post-trade reports,
- hypothesis generation,
- review recommendations,
- создание draft research notes.

Запрещенный scope:

- запись в Redis Streams deterministic core,
- изменение live risk parameters,
- отправка orders,
- отключение risk engine,
- auto-apply config changes.

## Confidence Note

Источник является documentation/source reference, но конкретная интеграция Hermes в CRYPTOTEHNOLOG еще не реализована. Поэтому confidence по проектной применимости - `medium`.

