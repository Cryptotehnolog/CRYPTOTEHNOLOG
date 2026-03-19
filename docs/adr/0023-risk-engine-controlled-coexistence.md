# Controlled coexistence нового Risk Engine runtime path с legacy core/listeners/risk.py

**Дата:** 2026-03-19  
**Статус:** Принято  

## Контекст
К моменту завершения Фазы 5 в проекте уже существовал legacy risk path на основе `core/listeners/risk.py` и связанной старой risk-логики. Одновременно Фаза 5 добавила новый `Risk Engine` как полноценный доменный, orchestration и runtime-контур.

Полная немедленная замена legacy-path на новый контур в масштабе всего проекта на этом этапе несла повышенный риск: слишком много точек bootstrap, runtime wiring и существующих зависимостей. Но скрытое смешивание двух risk-контуров было бы ещё хуже, потому что создало бы архитектурную двусмысленность и неявные конфликты источников истины.

## Рассмотренные альтернативы
1. Немедленно удалить legacy `core/listeners/risk.py` и полностью перевести проект на новый `Risk Engine`.
2. Скрыто подключить новый `Risk Engine` поверх legacy-path и дать им сосуществовать без явного архитектурного разграничения.
3. Оставить controlled coexistence: новый runtime path подключается отдельно и явно, а legacy-path не используется как база его реализации.

## Решение
Принят вариант 3.

- Новый `Risk Engine` собран как отдельный runtime path через `create_risk_runtime(...)`.
- Подключение к event-driven контуру выполняет отдельный `RiskEngineListener`.
- Optional persistence repository и `FundingManager` подключаются в новом контуре явно.
- Legacy `core/listeners/risk.py` не используется как основа новой реализации.
- Полная project-wide замена legacy-path сознательно не включена в scope Фазы 5.
- Сосуществование двух путей признаётся явно и рассматривается как временно контролируемое состояние архитектуры, а не как скрытая “магия совместимости”.

Кодовая опора решения:
- `src/cryptotechnolog/risk/runtime.py`
- `src/cryptotechnolog/risk/listeners.py`
- `src/cryptotechnolog/risk/engine.py`
- `src/cryptotechnolog/core/listeners/risk.py`

## Последствия
- **Плюсы:** Фаза 5 может быть завершена как рабочий релиз без широкого рискованного рефакторинга всего bootstrap; новый контур прозрачно отделён; упрощается controlled adoption в следующих шагах.
- **Минусы:** в проекте временно сосуществуют два risk-path; требуется дисциплина, чтобы не смешивать их в новых изменениях; полная консолидация архитектуры переносится на следующий этап.

## Связанные ADR
- Связан с `0021-risk-ledger-source-of-truth.md`
- Связан с `0022-trailing-policy-risk-engine-invariant.md`
