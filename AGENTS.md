# AGENTS.md

Этот файл задает рабочие правила для AI-агентов, которые работают в этом репозитории.

## Перед Работой

Перед изменениями в архитектуре, стратегиях, риск-модели, рыночных данных, исследовательском слое или базе знаний:

1. Прочитай `knowledge/schema.md`.
2. Прочитай `knowledge/index.md`.
3. Прочитай `knowledge/wiki/coding-standards.md`, если предстоит менять код, scripts, CI, Docker или Python/Rust tooling.
4. Открой релевантные страницы из `knowledge/wiki/`.
5. Проверь активные решения, отклоненные идеи, низкоуверенные допущения и известные риски.

Мелкие механические действия вроде `git status`, форматирования или чтения файла не требуют полного обзора wiki.

## Во Время Работы

- Делай небольшие, проверяемые изменения.
- Держи runtime-поведение торговой системы в коде, тестах, конфигах, миграциях и журналах событий (event logs).
- Для Rust-кода можно использовать локальный `rust-skills` как advisory review skill, но project-specific правила CRYPTOTEHNOLOG из `AGENTS.md` и `knowledge/` имеют приоритет.
- Не делай детерминированные торговые сервисы зависимыми от Markdown, Obsidian или LLM-сводок.
- Не делай Hermes Agent, OmniRoute или другие LLM tools частью execution path.
- Используй Hermes/OmniRoute только для research-layer задач: reports, hypotheses, post-trade analysis, draft recommendations.
- LightRAG документируется как future research-memory candidate, но до прохождения Phase 0 exit gate запрещены установка, Docker wiring, MCP wiring, ingestion данных в LightRAG и любые agent workflows, зависящие от LightRAG.
- Не сохраняй секреты, API-ключи, биржевые credentials или приватные данные счетов в базе знаний.

## После Работы

Если работа создает долговременное знание проекта, обнови:

1. релевантную страницу в `knowledge/wiki/`,
2. `knowledge/index.md`, если была добавлена новая страница,
3. `knowledge/graph.md`, если добавлена новая `decision` или `risk` страница и появилась важная смысловая связь,
4. `knowledge/log.md`.

`knowledge/graph.md` является curated-картой. Не добавляй туда каждую Markdown-ссылку; добавляй только важные связи `source -> concept`, `concept -> decision`, `decision -> risk`, `workflow -> automation script`.

Перед коммитом запусти:

```powershell
.\scripts\check_all.ps1
```

## Языковая Политика

Проектная документация пишется на русском языке.

Исключения остаются на английском:

- code identifiers,
- имена crates, modules, structs, functions,
- config keys,
- SQL table/column names,
- Redis stream names,
- API field names,
- имена файлов и директорий, если они являются техническими контрактами.

При первом упоминании важного технического термина используй русский текст и английский термин в скобках: например, `журнал событий (event journal)` или `детерминированное воспроизведение (deterministic replay)`.

## Политика Проверок

Pre-commit проверки должны оставаться быстрыми, локальными, детерминированными и без сети.

Они не должны:

- вызывать LLM,
- обращаться к внешним API,
- проверять внешние URL,
- запускать тяжелые тесты или длинные аудиты.

Если проверка становится медленной или требует сети, перенеси ее в CI или отдельный ручной audit script.
