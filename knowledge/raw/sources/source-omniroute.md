---
type: source
status: active
confidence: medium
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
source_id: omniroute-2026-05-20
title: OmniRoute Documentation
author: OmniRoute
created: 2026-05-20
url: https://omniroute.online/
---

# Source Note: OmniRoute

## Summary

OmniRoute рассматривается как local LLM gateway для research layer. Его роль - предоставить единый OpenAI-compatible endpoint для LLM calls и возможную MCP/tooling поверхность для AI agents.

Для CRYPTOTEHNOLOG OmniRoute не является trading component.

## Project Impact

Ожидаемый local endpoint:

```text
base_url = http://localhost:20128/v1
```

API key не должен храниться в wiki или Git. Использовать только environment variable, например:

```text
OMNIROUTE_API_KEY
```

## Caveats

- Количество MCP/tools и supported providers зависит от версии OmniRoute.
- Нельзя фиксировать в wiki точное число tools как стабильный contract без version pin.
- OmniRoute outage не должен влиять на deterministic core.

## Allowed Use

- LLM gateway для Hermes/research scripts.
- Offline/post-trade analysis.
- Hypothesis generation.
- Draft reports.

## Forbidden Use

- Direct order execution.
- Live risk decisions.
- Runtime dependency of strategy/risk/execution services.

