---
type: schema
status: active
owner: codex
updated: 2026-05-20
---

# Схема Базы Знаний

Этот документ задает правила, по которым Codex поддерживает базу знаний CRYPTOTEHNOLOG.

Операционный принцип основан на паттерне Karpathy LLM Wiki: raw sources остаются неизменяемыми, а Codex поддерживает постоянную связанную Markdown-wiki, которая накапливает ценность со временем.

## Структура Директорий

- `knowledge/raw/` - неизменяемые source notes и metadata источников. Codex может добавлять файлы сюда, но не должен переписывать существующие source captures, кроме исправления сломанной metadata.
- `knowledge/wiki/` - синтезированные страницы, которыми управляет Codex.
- `knowledge/templates/` - переиспользуемые page templates.
- `knowledge/index.md` - смысловая карта wiki.
- `knowledge/log.md` - append-only chronological maintenance log.
- `knowledge/schema.md` - этот operating contract.

## Типы Страниц

Каждая Markdown-страница, которой управляет Codex, должна использовать YAML frontmatter:

```yaml
---
type: concept|decision|source|workflow|risk|strategy|venue|metric|system
status: draft|active|superseded|rejected
confidence: low|medium|high
updated: YYYY-MM-DD
sources:
  - source-id
---
```

## Языковая Политика

Проектная документация пишется на русском языке.

Оставлять на английском нужно технические контракты:

- code identifiers,
- имена crates, modules, structs, functions,
- config keys,
- SQL table/column names,
- Redis stream names,
- API field names,
- имена файлов и директорий, если они являются техническим контрактом.

При первом упоминании важного технического термина используем русский текст и английский термин в скобках: `журнал событий (event journal)`, `детерминированное воспроизведение (deterministic replay)`, `источник истины (source of truth)`.

Не нужно делать bilingual-дублирование каждого раздела. Это увеличит стоимость поддержки.

## Правила Качества

Codex обязан:

- Разделять факты, допущения, мнения и решения.
- Ссылаться на raw source notes или канонические project files.
- Помечать неопределенные утверждения через `confidence: low` или явную оговорку.
- Обновлять `knowledge/index.md` после каждого knowledge-base edit.
- Добавлять запись в `knowledge/log.md` после каждого ingest, query synthesis, lint pass или крупной переработки.
- Предпочитать небольшие сфокусированные страницы большим монолитным заметкам.
- Создавать cross-links через relative Markdown links.
- Сохранять противоречивые утверждения, а не молча перетирать их.

Codex не должен:

- Считать model output источником истины.
- Переписывать immutable raw sources.
- Повышать hypothesis до decision без явной decision page.
- Прятать rejected ideas. Отклонения являются ценной project memory.
- Сохранять secrets, API keys, private credentials или exchange account details в wiki.

## Workflow Автоматизации

При обработке нового источника:

1. Создать raw source note в `knowledge/raw/sources/`.
2. Извлечь claims, assumptions, decisions и open questions.
3. Обновить или создать synthesized pages в `knowledge/wiki/`.
4. Добавить ссылки из затронутых страниц на raw source note.
5. Обновить `knowledge/index.md`.
6. Добавить dated entry в `knowledge/log.md`.
7. Запустить `scripts/kb_health_check.ps1`.

При ответе на архитектурный вопрос:

1. Прочитать `knowledge/index.md`.
2. Прочитать релевантные wiki pages.
3. Если ответ создает reusable synthesis, оформить его как wiki page.
4. Обновить `knowledge/log.md`.

При linting wiki:

1. Проверить missing frontmatter.
2. Проверить missing index entries.
3. Проверить stale `updated` dates.
4. Проверить orphan pages.
5. Проверить unresolved contradictions или low-confidence claims, которым нужны источники.

## Naming Conventions

Используем lowercase kebab-case filenames:

- `concept-probability-basis.md`
- `decision-first-mvp.md`
- `workflow-source-ingestion.md`
- `risk-settlement-mismatch.md`

## Source Identifiers

Используем stable IDs:

- `karpathy-llm-wiki-2026-04-04`
- `project-review-2026-05-19`
- `user-vision-2026-05-19`

