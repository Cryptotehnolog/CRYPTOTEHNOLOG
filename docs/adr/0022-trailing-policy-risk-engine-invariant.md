# TrailingPolicy как часть Risk Engine и инвариант No stop move without RiskLedger sync

**Дата:** 2026-03-19  
**Статус:** Принято  

## Контекст
Во Фазе 5 был реализован новый `TrailingPolicy` для управления стопом открытой позиции.

Ключевая проблема состояла в том, что trailing logic можно было реализовать по-розничному: как вспомогательную стратегическую эвристику, которая двигает стоп независимо от risk-контра. Для институционального risk loop это недопустимо. Trailing влияет на downside risk позиции и поэтому должен быть встроен в доменную модель риска, а не жить как отдельная торговая эвристика.

Особенно критично это для MFT/SFT risk-контура, где stop move напрямую меняет aggregate risk и должен быть синхронизирован с позицией, ledger и audit trail.

## Рассмотренные альтернативы
1. Оставить trailing в strategy-слое и передавать в `Risk Engine` уже готовый новый стоп.
2. Реализовать trailing внутри `Risk Engine`, но допускать локальный stop move с последующим best-effort обновлением ledger.
3. Сделать `TrailingPolicy` частью `Risk Engine` и разрешать stop move только после успешного `RiskLedger sync`.

## Решение
Принят вариант 3.

- `TrailingPolicy` принадлежит `Risk Engine`, а не strategy-слою.
- Trailing использует доменные модели позиции и риск-записи, а не transport payload.
- Движение стопа не допускается до arm threshold.
- Любой допустимый stop move сначала проходит через `RiskLedger.update_position_risk(...)`.
- При любой ошибке синхронизации с ledger реальный move блокируется.
- `TrailingPolicy` поддерживает явные состояния, tiers и modes, а trailing history различает `MOVE`, `BLOCKED`, `STATE_SYNC`, `TERMINATE`.
- `terminate` и state-only paths имеют явную audit-семантику и не притворяются обычным pnl-based trailing move.

Кодовая опора решения:
- `src/cryptotechnolog/risk/trailing_policy.py`
- `src/cryptotechnolog/risk/risk_ledger.py`
- `src/cryptotechnolog/risk/models.py`
- `src/cryptotechnolog/risk/engine.py`

## Последствия
- **Плюсы:** trailing перестаёт быть скрытой стратегической логикой; риск не может измениться без ledger sync; audit trail становится однозначным; проще удерживать монотонность стопа и запрет роста downside risk.
- **Минусы:** trailing path становится более строгим и менее “гибким” для стратегии; требуется дополнительная дисциплина в orchestration; некоторые потенциально выгодные stop updates теперь корректно блокируются при ошибках ledger sync.

## Связанные ADR
- Связан с `0021-risk-ledger-source-of-truth.md`
- Связан с `0023-risk-engine-controlled-coexistence.md`
