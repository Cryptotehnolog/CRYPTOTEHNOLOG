# CRYPTOTEHNOLOG

Детерминированная исследовательская и торговая инфраструктура для проверки crypto probability-basis идей.

Первый MVP намеренно узкий: сравнивать вероятности, подразумеваемые ETH-опционами Deribit, с ценами событий Polymarket, сохранять наблюдения и проверять, переживает ли спред комиссии, bid/ask spread, проскальзывание (slippage), несовпадение settlement и ограничения ликвидности.

Live trading не входит в первый MVP.

## Текущее Решение

Мы начинаем с `Deribit + Polymarket probability_basis`, а не с funding carry.

Пока это не называется арбитражем. Текущая цель - собрать доказательства:

- Можно ли надежно находить соответствующие события?
- Достаточно ли близко совпадают expiry и settlement definitions?
- Есть ли ликвидность с обеих сторон?
- Переживает ли наблюдаемый спред расчетные издержки?
- Можно ли детерминированно воспроизвести один и тот же raw event log?

## Структура Репозитория

- `crates/common` - канонические Rust event contracts.
- `crates/replay` - каркас детерминированного воспроизведения (deterministic replay).
- `config/` - human-approved конфиги стратегий, риска, площадок и инструментов.
- `knowledge/` - база знаний проекта, поддерживаемая LLM.
- `migrations/` - PostgreSQL schema для event sourcing и observations.
- `research/` - будущие Python-скрипты и notebooks для исследований.
- `scripts/` - локальные automation scripts.
- `tests/` - будущие Python tests.
- `PROJECT_REVIEW.md` - стартовый инженерный review.

## Локальная Инфраструктура

PostgreSQL является источником истины (source of truth). Redis будет использоваться как временная message bus после стабилизации контрактов.

Запустить локальную инфраструктуру:

```powershell
docker compose up -d
```

Запустить текущий Rust replay smoke test:

```powershell
cargo run -p cryptotehnolog-replay
```

Проверить здоровье базы знаний:

```powershell
.\scripts\kb_health_check.ps1
```

Проверить локальные Markdown-ссылки:

```powershell
.\scripts\validate_local_links.ps1
```

Проверить устаревание knowledge pages в warning-only режиме:

```powershell
.\scripts\kb_stale_check.ps1
```

Запустить все быстрые локальные проверки:

```powershell
.\scripts\check_all.ps1
```

Показать состояние проекта перед рабочей сессией:

```powershell
.\scripts\dev_status.ps1
```

Создать raw source note:

```powershell
.\scripts\new_source_note.ps1 -Title "Source title" -Url "https://example.com"
```

## База Знаний

Проект использует локальную Markdown-базу знаний по паттерну Karpathy LLM Wiki.

- Raw source notes живут в `knowledge/raw/`.
- Синтезированные страницы проекта живут в `knowledge/wiki/`.
- Рабочий контракт описан в `knowledge/schema.md`.
- `knowledge/index.md` - смысловая карта базы знаний.
- `knowledge/log.md` - append-only журнал обслуживания.

Codex должен автоматически обновлять базу знаний, когда появляется долговременное проектное решение, анализ источника, risk critique или переиспользуемый synthesis.

Правило использования Codex:

- перед архитектурным или стратегическим кодом читать `knowledge/index.md` и релевантные wiki-страницы;
- после долговременных решений или reusable analysis обновлять релевантную wiki-страницу, `knowledge/index.md` и `knowledge/log.md`;
- перед коммитом knowledge changes запускать `.\scripts\kb_health_check.ps1`.

Использование Obsidian:

- открыть `D:\CRYPTOTEHNOLOG\knowledge` как Obsidian vault;
- использовать для чтения, graph navigation, backlinks и ручного review;
- не делать Obsidian plugins runtime-зависимостью торговой системы.

## Языковая Политика

Проектная документация пишется на русском языке.

Технические контракты остаются на английском: code identifiers, config keys, SQL names, Redis stream names, API fields, имена crates/modules и пути. При первом упоминании важных терминов используем русский текст и английский термин в скобках.

## Риск-Позиция

Ограничения MVP:

- Нет live orders.
- AI agent не участвует в execution path.
- Нет Kelly sizing.
- Нет short Deribit options.
- Нет short Polymarket outcomes.
- PostgreSQL event journal идет перед derived features.
- Deterministic replay идет перед real ingestion.

## Следующие Улучшения Для Автоматизации

1. Добавить Windows-friendly аналоги `justfile` или `Makefile`.
2. Добавить migration runner.
3. Добавить deterministic replay tests.
4. Добавить JSON serialization, когда будут разрешены внешние зависимости.
5. Добавить Deribit и Polymarket discovery adapters за traits.
6. Добавить отчет, который перечисляет candidate market pairs и отклоняет плохие matches с причинами.
