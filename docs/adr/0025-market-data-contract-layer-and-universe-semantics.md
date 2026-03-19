# Market Data contract layer и universe semantics внутри текущей архитектуры

**Дата:** 2026-03-19  
**Статус:** Принято  

## Контекст
Фаза `P_6` открывает новую feature-line после завершённой `P_5_1`.

После `v1.5.1` у проекта уже есть:
- единый production composition root;
- один активный production risk path;
- runtime truth для version/config/bootstrap/risk path;
- единый Event Bus style и lifecycle discipline;
- Control Plane semantics, которые нельзя обходить ad-hoc runtime-компонентами.

Исходный prompt Фазы 6 силён по смыслу, но в исходном виде содержит архитектурную двусмысленность:
- использует устаревший package path вида `src/market_data/...`;
- описывает event publication как свободные dict payloads без привязки к текущему event contract;
- местами создаёт впечатление, что `UniverseEngine` сам двигает состояние системы;
- смешивает обязательный `raw/admissible` scope Фазы 6 с future-line ranked/opportunity semantics.

Перед runtime-реализацией нужен contract lock, чтобы `Market Data Layer` не стал новым параллельным слоем со своей локальной архитектурой.

## Рассмотренные альтернативы
1. Начать `P_6` сразу с runtime ingestion/websocket manager и уточнять контракты по ходу.
2. Сохранить исходный prompt-layout как есть и строить новый слой вне текущего package layout проекта.
3. Ограничиться только data models без фиксации event vocabulary и universe semantics.
4. Сначала зафиксировать contract layer внутри `src/cryptotechnolog/market_data`, связать его с текущим `Event Bus`/`Control Plane` стилем и только потом переходить к runtime foundation.

## Решение
Принят вариант 4.

### 1. Package path Phase 6
- Весь Python-layer Фазы 6 живёт внутри `src/cryptotechnolog/market_data`.
- Новый слой не создаёт отдельного верхнеуровневого `src/market_data`.
- Contract-first модули Фазы 6 фиксируются через:
  - `market_data/models.py`
  - `market_data/events.py`
  - `market_data/__init__.py`

### 2. Typed contracts до runtime
До runtime-реализации фиксируются typed models для:
- `TickContract`
- `OHLCVBarContract`
- `OrderBookSnapshotContract`
- `SymbolContract`
- `SymbolMetricsContract`
- `DataQualitySignal`
- `RawUniverseSnapshot`
- `AdmissibleUniverseSnapshot`
- `RankedUniverseSnapshot`
- `UniverseQualityAssessment`

Эти контракты transport-neutral и не создают bootstrap/runtime side effects.

### 3. Один event style для Market Data Layer
- Market data события публикуются только через существующий `Event`/`EnhancedEventBus` contract.
- Вводится Phase 6 vocabulary, совместимый с текущим event layer:
  - `TICK_RECEIVED`
  - `BAR_COMPLETED`
  - `ORDERBOOK_UPDATED`
  - `SYMBOL_METRICS_UPDATED`
  - `UNIVERSE_RAW_UPDATED`
  - `UNIVERSE_ADMISSIBLE_UPDATED`
  - `UNIVERSE_RANKED_UPDATED`
  - `UNIVERSE_CONFIDENCE_UPDATED`
  - `UNIVERSE_CONFIDENCE_LOW`
  - `UNIVERSE_READY`
  - `UNIVERSE_EMPTY`
  - `SYMBOL_ADMITTED_TO_UNIVERSE`
  - `SYMBOL_REMOVED_FROM_UNIVERSE`
  - `DATA_GAP_DETECTED`
  - `MARKET_DATA_STALE`
  - `MARKET_DATA_OUTLIER_DETECTED`
  - `MARKET_DATA_SOURCE_DEGRADED`
- Для этих событий фиксируются typed payload contracts и default priority policy.

### 4. Universe semantics
- `universe_raw` обязателен как versioned snapshot всех обнаруженных символов.
- `universe_admissible` обязателен как versioned snapshot символов, прошедших liquidity/quality/policy filters.
- `universe_ranked` фиксируется как future-ready contract и snapshot API, но не как обязательная полнофункциональная OpportunityEngine-реализация внутри Step 1.
- `UniverseQualityAssessment` становится отдельным operator/runtime contract:
  - `confidence`
  - `state = ready/degraded/blocked`
  - `raw_count`
  - `admissible_count`
  - `ranked_count`
  - `blocking_reasons`
  - `worst_symbols`

### 5. Control Plane discipline
- `UniverseEngine` не выполняет произвольные state transitions напрямую.
- Market Data Layer публикует типизированные сигналы о качестве данных и качестве universe.
- Решения о state/degradation/readiness принимаются через существующий orchestration path следующими шагами `P_6`, а не скрыто внутри contract layer.

## Последствия
- **Плюсы:** Step 2 получает ясный package path и typed foundation без архитектурной двусмысленности.
- **Плюсы:** `Market Data Layer` сразу совместим с runtime discipline, введённой в `P_5_1`.
- **Плюсы:** `UniverseEngine` фиксируется как risk-relevant gate на admissible universe, а не как локальная ranking-фича.
- **Минусы:** часть исходного prompt становится уже, чем его первоначальная “широкая” формулировка.
- **Минусы:** ranked/opportunity semantics пока фиксируются как contract-ready слой, а не как сразу готовый runtime.

## Документационная синхронизация после реализации P_6
- Для фактически реализованного scope Phase 6 единым runtime entrypoint считается `cryptotechnolog.market_data.runtime.MarketDataRuntime`.
- Universe orchestration текущей фазы реализуется через `UniversePolicy` и explicit runtime methods `MarketDataRuntime`, а не через отдельный scheduler-style `UniverseEngine` сервис.
- WebSocket/feed manager и persistence/storage path не считаются частью завершённого mandatory scope `P_6`; это future-line расширения.
- Любые prompt/plan ссылки на `MarketDataManager`, `UniverseEngine`, `websocket.py` или `timescale_writer.py` в рамках closure `P_6` должны читаться только через эту нормализацию, если они не подтверждены фактическим кодом.

## Связанные ADR
- Связан с `0021-risk-ledger-source-of-truth.md`
- Связан с `0022-trailing-policy-risk-engine-invariant.md`
- Связан с `0023-risk-engine-controlled-coexistence.md`
- Связан с `0024-production-alignment-composition-root-and-runtime-truth.md`
