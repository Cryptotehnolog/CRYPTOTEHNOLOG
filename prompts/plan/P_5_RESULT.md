# Фаза 5: Risk Engine — итоговый summary

## Краткое summary фазы

Фаза 5 завершена как релиз `v1.5.0`. В проект добавлен новый контур `Risk Engine` в Python как отдельная современная ветка архитектуры: с доменными моделями, pre-trade orchestration, event-driven integration, persistence/audit foundation и runtime/bootstrap integration.

Новый risk-контур собран без опоры на legacy `core/listeners/risk.py` как на основу реализации. При этом полная замена legacy-path в масштабе всего проекта сознательно оставлена как controlled coexistence для следующего этапа внедрения.

## Что реализовано

- Доменные модели `Risk Engine` для ордеров, позиций, risk-records, trailing и funding.
- `PositionSizer` с `Decimal`-математикой и `R-unit` логикой расчёта позиции.
- Позиционный `RiskLedger` как единый источник истины по риску открытых позиций.
- `TrailingPolicy` с состояниями, tier-based trailing, режимами `NORMAL / STRUCTURAL / EMERGENCY` и инвариантом `No stop move without RiskLedger sync`.
- `PortfolioState` и `DrawdownMonitor` как foundation для aggregate risk/exposure и pre-trade risk gates.
- `Correlation` layer для pre-trade ограничения связанных позиций.
- `FundingManager` как отдельный доменный модуль фазы.
- `RiskEngine` как первый orchestration-слой:
  - pre-trade checks;
  - event-driven обработка `ORDER_FILLED`, `POSITION_CLOSED`, `BAR_COMPLETED`, `STATE_TRANSITION`.
- `RiskEngineListener` как тонкий адаптер к event-driven контуру.
- Persistence/schema foundation для:
  - `risk_checks`;
  - `position_risk_ledger`;
  - `position_risk_ledger_audit`;
  - `trailing_stops`;
  - `trailing_stop_movements`.
- Optional repository integration и runtime wiring через `create_risk_runtime(...)`.

## Ключевые архитектурные решения

- Новый `Risk Engine` реализован как отдельный доменный и orchestration-контур Фазы 5, а не как развитие legacy listener-логики.
- `RiskLedger` зафиксирован как source of truth по риску открытых позиций; aggregate risk больше не должен выводиться из побочных структур.
- Контракт синхронизации `RiskLedger <-> PortfolioState` сделан явным, а не неявным соглашением.
- `TrailingPolicy` принадлежит `Risk Engine`, а не стратегии; движение стопа допускается только при успешном `RiskLedger sync`.
- Persistence подключается как optional dependency и не делает `RiskEngine` зависимым от БД при обычном импорте.
- Runtime integration нового risk-контура оставлена отдельной и прозрачной; coexistence с legacy-path контролируемое, а не скрытое.

## Что не вошло в scope

- Полная project-wide замена legacy `core/listeners/risk.py`.
- Глубокая production adoption нового risk-контура во всех верхнеуровневых bootstrap-path.
- Расширенная funding integration в основной trade loop.
- Более тяжёлая статистическая/матричная correlation model.
- Дополнительные production runbooks и операционные процедуры вокруг нового risk-контура.
- Линия dashboard/panel не входила в релиз `v1.5.0`.

## Результат релиза

- Версия: `v1.5.0`
- Релизный коммит: `70f7797` (`release: v1.5.0`)
- Тег: `v1.5.0`
- Merge status: релизная ветка Фазы 5 была чисто слита в `master`

## Состояние проекта после Фазы 5

После завершения Фазы 5 проект получил законченный foundation нового `Risk Engine` с доменной моделью, risk orchestration, audit/persistence basis и runtime integration path. Это уже не stub и не частичная заготовка, а рабочий phase-complete контур `v1.5.0`, пригодный для controlled adoption в верхнем bootstrap проекта и для дальнейшего развития следующими фазами без архитектурной двусмысленности.
