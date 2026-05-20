---
type: system
status: active
confidence: medium
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
sources:
  - omniroute-2026-05-20
---

# Tool: OmniRoute

OmniRoute - локальный LLM gateway для research layer CRYPTOTEHNOLOG.

Он должен использоваться как единая точка доступа к LLM providers для Hermes Agent и будущих research scripts.

## Endpoint

Ожидаемый локальный endpoint:

```text
base_url = http://localhost:20128/v1
```

API key не хранится в wiki, Git или config files.

Использовать environment variable:

```text
OMNIROUTE_API_KEY
```

## Role

Разрешено:

- LLM calls для post-trade analysis,
- summarization research reports,
- hypothesis generation,
- routing/fallback между providers,
- experiments вне deterministic execution path.

Запрещено:

- принимать live trading decisions,
- менять risk parameters,
- писать в Redis Streams ядра,
- быть обязательной dependency для deterministic services.

## MCP Note

OmniRoute может предоставлять MCP/tooling capabilities, но количество tools и конкретный набор capabilities зависят от версии. Не фиксировать в проектных contracts точное число tools без version pin.

## Failure Mode

Если OmniRoute недоступен, deterministic core должен продолжать работать. Research reports могут быть отложены.

