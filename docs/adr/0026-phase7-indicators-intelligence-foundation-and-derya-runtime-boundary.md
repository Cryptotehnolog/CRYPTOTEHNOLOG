# Phase 7 Indicators + Intelligence Foundation и runtime boundary DERYA

**Дата:** 2026-03-20  
**Статус:** Принято  

## Контекст
Фаза `P_7` открывается после завершённой `P_6`, где уже зафиксирован contract-first
`Market Data Layer` и explicit runtime discipline внутри текущей архитектуры проекта.

К этому моменту у платформы уже есть:
- единый production composition root;
- runtime truth для version/config/bootstrap/health/shutdown;
- один активный production risk path;
- contract-first `Market Data Layer` в `src/cryptotechnolog/market_data`;
- typed contract на `BAR_COMPLETED`, который может служить честным upstream input для intelligence-layer.

Одновременно исходный prompt Фазы 7 остаётся слишком широким:
- смешивает indicator/intelligence line с signal/strategy line;
- тянет устаревший package layout;
- местами описывает DERYA так, как будто это microstructure engine;
- не фиксирует, что first-class truth нового фактора должна жить в state/query contract, а не только в событиях.

После contract lock и реализации stateful DERYA machine нужен ADR, который:
- закрепляет обязательную truth-картину `P_7`;
- запрещает scope inflation в сторону `P_8`;
- фиксирует runtime boundary следующего implementation step без преждевременного bootstrap wiring.

## Рассмотренные альтернативы
1. Оставить `P_7` как широкий “intelligence + signal preparation” этап и разрешить постепенное смешение с future strategy line.
2. Оформить DERYA как event-first фактор, где основная truth живёт в `DERYA_REGIME_CHANGED`, а query/state являются вторичными helper-API.
3. Описывать DERYA как качественную или квази-микроструктурную модель без жёсткой формализации smoothing/acquisition/neutral-zone semantics.
4. Зафиксировать `P_7` как `Indicators + Intelligence Foundation`, отделить её от signal/strategy line, оформить DERYA как отдельный `OHLCV bar-efficiency proxy` factor со state/query-first contract и определить узкий runtime boundary через explicit intelligence runtime entrypoint.

## Решение
Принят вариант 4.

### 1. Scope truth Phase 7
- `P_7` является `Indicators + Intelligence Foundation`.
- Фаза 7 не смешивается с `SignalGenerator`, `OpportunityEngine`, `MetaClassifier`, `StrategyManager` и standalone strategy line.
- Любые signal/strategy semantics остаются отдельной future-line и не могут вводиться ad hoc под видом intelligence convenience.

### 2. Package path Phase 7
- Новый код `P_7` живёт внутри `src/cryptotechnolog/intelligence`.
- При необходимости допустим `src/cryptotechnolog/analysis`, но `P_7` не вводит новый верхнеуровневый `src/indicators`.
- Phase 7 package surface фиксируется через:
  - `intelligence/models.py`
  - `intelligence/events.py`
  - `intelligence/derya_engine.py`
  - `intelligence/runtime.py`
  - `intelligence/__init__.py`

### 3. DERYA как отдельный intelligence factor
- DERYA допустим только как отдельный intelligence factor внутри `P_7`.
- DERYA честно определяется как `OHLCV bar-efficiency proxy`.
- DERYA не считается:
  - tick-level microstructure engine;
  - order-flow engine;
  - signal generator;
  - strategy filter по умолчанию.

### 4. Mathematical truth DERYA
- Bar-efficiency определяется как:
  - `abs(close - open) / (high - low)`
- Zero-range / flat bars не считаются special alpha-signal и обрабатываются честно как `0`.
- Smoothing в текущей реализации фиксируется явно:
  - используется trailing arithmetic mean последних `N` raw efficiency values;
  - `N` задаётся через `smoothing_window`;
  - это и есть текущий smoothing rule, а не placeholder для “магического” фильтра.
- Slope определяется как разность между текущим smoothed value и предыдущим smoothed value.

### 5. Deterministic regime machine
- Для DERYA допускаются ровно 4 режима:
  - `EXPANSION`
  - `EXHAUSTION`
  - `COLLAPSE`
  - `RECOVERY`
- Эти режимы задаются детерминированно через:
  - `high_efficiency_threshold`
  - `low_efficiency_threshold`
  - `slope_flat_threshold`
  - `hysteresis_band`
  - `min_persistence_bars`
- Neutral zone между high/low thresholds не порождает новый режим автоматически.
- В neutral zone engine обязан:
  - либо удерживать previous regime через carry-forward/hysteresis;
  - либо оставлять factor в not-ready / non-transitioned semantics;
  - но не создавать дополнительные qualitative labels.

### 6. Initial regime acquisition
- Initial regime acquisition из `None` в первый режим трактуется явно.
- Первый режим считается acquired только после того, как engine достиг readiness по history requirements и увидел валидный regime candidate.
- Это initial acquisition является таким же stateful regime decision, как и дальнейшие transitions, а не “случайным” fallback-поведением.
- Initial acquisition не должна маскироваться под background bootstrap или implicit default regime.

### 7. State/query truth важнее event truth
- First-class truth для DERYA — это state/query contract:
  - текущий `DeryaAssessment`;
  - recent regime history;
  - recent raw/smoothed efficiency series.
- Event layer вторичен и дополняет state/query API.
- `DERYA_REGIME_CHANGED` публикуется только для подтверждённого transition и не считается единственным источником истины о текущем режиме.

### 8. Local event vocabulary Phase 7
- Для `P_7` допустим локальный `IntelligenceEventType`.
- Это phase-level vocabulary, а не отдельный параллельный системный event universe.
- Такой vocabulary допустим, пока он:
  - transport-compatible с существующим `Event` contract;
  - не внедряет trading-signal semantics;
  - не подменяет composition-root discipline.

### 9. Runtime boundary следующего implementation step
- Следующим explicit runtime entrypoint intelligence-layer считается `cryptotechnolog.intelligence.runtime.IntelligenceRuntime`.
- Этот runtime:
  - не создаёт import-time side effects;
  - не выполняет hidden bootstrap;
  - не подписывается сам на Event Bus на import path;
  - получает `BAR_COMPLETED` через явный orchestration/wiring layer следующего шага.
- Базовый ingest path следующего шага:
  1. runtime получает completed bar как typed `OHLCVBarContract` или typed `BarCompletedPayload`;
  2. runtime преобразует payload в typed bar contract;
  3. runtime обновляет `DeryaEngine`;
  4. runtime возвращает typed update result;
  5. при подтверждённом regime transition runtime может сформировать `DERYA_REGIME_CHANGED`.
- Query surface DERYA экспонируется наружу через explicit methods runtime-а, а не через скрытый global state.

### 10. Readiness и degradation semantics следующего шага
- Intelligence runtime должен различать:
  - `not_started`
  - `warming`
  - `ready`
  - `degraded`
  - `stopped`
- Недостаток bar history не считается silently-ready состоянием.
- Degradation и non-ready semantics должны быть operator-visible и совместимыми с существующей runtime truth discipline.
- Никакой hidden bootstrap, background singleton или import-time wiring не допускается.

## Последствия
- **Плюсы:** `P_7` получает жёсткую защиту от расползания в `P_8`.
- **Плюсы:** DERYA фиксируется честно и инженерно объяснимо, без ложной микроструктурной мифологии.
- **Плюсы:** state/query contract становится primary truth и создаёт хороший фундамент для runtime integration и observability.
- **Плюсы:** следующий implementation step по runtime уже имеет ясный entrypoint и ingest path от `BAR_COMPLETED`.
- **Минусы:** event-first shortcuts и быстрые “strategy helper” обходы теперь считаются архитектурным нарушением.
- **Минусы:** intelligence runtime придётся интегрировать дисциплинированно, а не как локальный helper рядом с market data.

## Что становится обязательным для следующего implementation step
1. Реализовать `IntelligenceRuntime` как explicit runtime shell внутри `src/cryptotechnolog/intelligence/runtime.py`.
2. Подключить ingest path от `BAR_COMPLETED` через явный wiring, а не через import-time подписки.
3. Пробросить DERYA query surface наружу через runtime API.
4. Зафиксировать readiness/diagnostics semantics для intelligence-layer без hidden bootstrap.
5. Сохранять separation между analysis truth и future signal/strategy line.

## Связанные ADR
- Связан с `0024-production-alignment-composition-root-and-runtime-truth.md`
- Связан с `0025-market-data-contract-layer-and-universe-semantics.md`
