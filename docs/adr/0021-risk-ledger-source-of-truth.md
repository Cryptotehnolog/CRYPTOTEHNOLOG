# RiskLedger как source of truth по риску позиций и явная синхронизация с PortfolioState

**Дата:** 2026-03-19  
**Статус:** Принято  

## Контекст
Фаза 5 (`Risk Engine`) добавила новый позиционный контур управления риском в Python.

Внутри этого контура появились два разных представления открытых позиций:
- `RiskLedger` как реестр текущего и исходного downside risk по каждой позиции;
- `PortfolioState` как snapshot открытых позиций для aggregate exposure, aggregate risk и будущих pre-trade checks.

Без явного архитектурного решения эти два компонента легко превратить в два независимых источника истины. Это особенно опасно для MFT/SFT и операторского risk-контра, где ошибка синхронизации может привести к неверной оценке aggregate risk, ложным reject/allow в pre-trade path и некорректному trailing behavior.

## Рассмотренные альтернативы
1. Сделать `PortfolioState` самостоятельным источником истины и считать aggregate risk напрямую из него.
2. Держать `RiskLedger` и `PortfolioState` как независимые структуры и полагаться на дисциплину вызовов в orchestration-слое.
3. Зафиксировать `RiskLedger` как source of truth по риску, а `PortfolioState` сделать синхронизируемым производным snapshot-слоем.

## Решение
Принят вариант 3.

- `RiskLedger` зафиксирован как единственный источник истины по downside risk открытых позиций.
- `PortfolioState` не принимает самостоятельных risk-решений и не считается авторитетным источником для risk math.
- Контракт синхронизации сделан явным через методы `sync_position_from_ledger(...)`, `release_position_from_ledger(...)`, `assert_position_matches_ledger(...)`, `assert_total_risk_matches_ledger(...)`.
- `RiskEngine` обязан синхронизировать `PortfolioState` после register/update/release операций в `RiskLedger`.
- Aggregate risk в pre-trade path валидируется против данных `RiskLedger`, а exposure и позиционный snapshot читаются из `PortfolioState`.

Кодовая опора решения:
- `src/cryptotechnolog/risk/risk_ledger.py`
- `src/cryptotechnolog/risk/portfolio_state.py`
- `src/cryptotechnolog/risk/engine.py`

## Последствия
- **Плюсы:** риск позиции считается в одном месте; легче удерживать инварианты; проще audit и reasoning для pre-trade checks; следующий слой orchestration не может незаметно разъехать `RiskLedger` и `PortfolioState`.
- **Минусы:** появляется явный sync-contract, который нужно соблюдать во всех event-driven path; orchestration получает дополнительную обязанность по синхронизации; некоторые ошибки теперь проявляются жёстко, а не скрыто.

## Связанные ADR
- Связан с `0022-trailing-policy-risk-engine-invariant.md`
- Связан с `0023-risk-engine-controlled-coexistence.md`
