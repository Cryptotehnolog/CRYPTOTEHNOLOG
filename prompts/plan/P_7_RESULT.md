# Фаза 7: Indicators + Intelligence Foundation — итоговый summary

## Краткое summary фазы

Фаза 7 завершена как phase-closure линия `v1.7.0` в честной форме
`DERYA-first intelligence foundation`, дополненная corrective line `C_7R`.

В проект добавлен production-compatible intelligence contour поверх уже завершённого
`Market Data Layer`: с typed contracts, stateful `DeryaEngine`, explicit
`IntelligenceRuntime`, composition-root integration, operator-visible
readiness/degradation truth.

После аудита release-blocker по active risk contour был снят отдельной corrective line
`C_7R`, которая ввела shared analysis truth для derived inputs `ATR/ADX` и честно
восстановила production-compatible path до `RISK_BAR_COMPLETED`.

Ключевая нормализация closure truth:
- `P_7` не притворяется полной classical indicator/runtime line;
- `P_7` не заходит в `SignalGenerator`, strategy-management и dashboard track;
- first-class реализация текущей фазы — это DERYA как честный
  `OHLCV bar-efficiency proxy`;
- derived inputs для active risk contour (`ATR/ADX`) входят в итоговую release truth
  только через отдельный shared analysis layer, а не через задним числом приписанную
  broad indicator runtime.

## Что реализовано

- Typed contracts для indicator snapshot/value semantics и intelligence assessments.
- Local analysis event vocabulary для Phase 7 внутри `src/cryptotechnolog/intelligence`.
- `DeryaAssessment`, `DeryaClassificationBasis`, `DeryaResolutionState` и related query/event contracts.
- `DeryaEngine` как deterministic stateful regime machine с:
  - `EXPANSION`
  - `EXHAUSTION`
  - `COLLAPSE`
  - `RECOVERY`
- Честный `bar_efficiency = abs(close - open) / (high - low)` с корректной zero-range semantics.
- Smoothing, slope, hysteresis, persistence, carry-forward и non-ready semantics для DERYA.
- Explicit `IntelligenceRuntime` как runtime entrypoint intelligence-layer.
- Narrow composition-root wiring от raw market-data `BAR_COMPLETED` через существующий production bootstrap.
- Shared bar boundary нормализована: risk contour больше не использует market-data `BAR_COMPLETED` как свой trailing event contract.
- `SharedAnalysisRuntime` как отдельный shared analysis source/truth layer для `ATR/ADX`.
- Query/state-first contracts для shared derived inputs active risk contour.
- Raw `BAR_COMPLETED` теперь параллельно обновляет:
  - `IntelligenceRuntime` для DERYA-first линии;
  - `SharedAnalysisRuntime` для derived analysis truth.
- `RISK_BAR_COMPLETED` публикуется только при наличии полного набора truth sources:
  - `mark_price` из completed bar;
  - `best_bid` / `best_ask` из orderbook truth;
  - `ATR` / `ADX` из shared analysis truth.
- Operator-facing diagnostics и readiness/degradation truth для intelligence runtime.
- Operator-facing diagnostics и readiness/degradation truth для shared analysis runtime.
- Unit, regression и Redis-backed integration verification для DERYA-first runtime line и corrective risk-input recovery path.

## Ключевые архитектурные решения

- `P_7` закрыта как `Indicators + Intelligence Foundation`, но её first-class closure scope
  нормализован до DERYA-first линии, подтверждённой фактическим кодом.
- DERYA закреплён как отдельный intelligence factor, а не как скрытый signal helper или
  ложный microstructure engine.
- First-class truth для DERYA живёт в state/query contracts; event layer вторичен.
- `DERYA_REGIME_CHANGED` публикуется как typed analysis event только для подтверждённого transition.
- `IntelligenceRuntime` входит в composition root явно и не создаёт import-time/bootstrap side effects.
- `ATR/ADX` закреплены за `src/cryptotechnolog/analysis`, а не за raw market data и не за risk layer.
- `SharedAnalysisRuntime` является corrective runtime foundation для derived inputs active risk contour.
- `RISK_BAR_COMPLETED` восстановлен как отдельный risk-specific event boundary поверх полного набора production truth.
- Readiness/degradation truth Phase 7 встроена в существующую runtime discipline,
  а не оформлена как параллельная health universe.
- Event Bus semantics не были искажены ради closure: handler errors в `publish(...)`
  остаются logged/operator-visible, но не становятся новым fail-fast contract.

## Что не вошло в scope

- Полная classical indicator runtime/library.
- `IndicatorRuntime` как широкий production contour для набора RSI / MACD / ATR / ADX / Bollinger / Donchian.
- Config hot-reload contour для broader indicator/intelligence line.
- `SignalGenerator`, `OpportunityEngine`, `MetaClassifier`, `StrategyManager`.
- Strategy integration и `DeryaBreakoutStrategy`.
- Dashboard-led observability и UI track.
- Любая `P_8` signal/strategy semantics.

## Verification truth

Реально выполненные проверки:

- `.venv\Scripts\python.exe -m py_compile src/cryptotechnolog/analysis/runtime.py src/cryptotechnolog/bootstrap.py src/cryptotechnolog/core/health.py tests/unit/test_analysis_runtime.py tests/unit/test_bootstrap.py tests/integration/test_bootstrap_integration.py`
- `.venv\Scripts\python.exe -m pytest -rs tests/unit/test_analysis_runtime.py tests/unit/test_bootstrap.py tests/integration/test_bootstrap_integration.py`
- `.venv\Scripts\ruff.exe format --check --preview src/cryptotechnolog/analysis/runtime.py src/cryptotechnolog/bootstrap.py src/cryptotechnolog/core/health.py tests/unit/test_analysis_runtime.py tests/unit/test_bootstrap.py tests/integration/test_bootstrap_integration.py README.md prompts/plan/P_7.md prompts/plan/P_7_RESULT.md`
- `.venv\Scripts\ruff.exe check src/cryptotechnolog/analysis/runtime.py src/cryptotechnolog/bootstrap.py src/cryptotechnolog/core/health.py tests/unit/test_analysis_runtime.py tests/unit/test_bootstrap.py tests/integration/test_bootstrap_integration.py`
- Redis-backed verification:
  - `docker compose up -d redis`
  - `.venv\Scripts\python.exe -m pytest -rs tests/integration/test_bootstrap_integration.py`
  - `docker compose stop redis`

Итог verification:

- unit/regression/bootstrap subset — зелёный;
- `ruff format --check --preview` и `ruff check` — зелёные;
- Redis-backed `test_bootstrap_integration.py` — `5 passed`;
- environment-specific nuance: `PytestCacheWarning` из-за denied access к `.pytest_cache`,
  но это не блокировало verification и не исказило результат.

## Follow-up lines после closure

- Широкая indicator runtime/library line.
- Config/hot-reload line для broader intelligence contour.
- `P_8` как отдельная signal-generation / opportunity line.
- Любая strategy/execution integration, использующая DERYA как consumer, а не как phase truth.

## Состояние проекта после Фазы 7

После завершения `P_7` платформа получила не абстрактный “analysis someday” слой,
а формально собранный DERYA-first intelligence foundation поверх `MarketDataRuntime`,
дополненный shared analysis truth для derived inputs active risk contour.

Это уже достаточная и честная основа для следующей отдельной линии,
но без ложного утверждения, что у проекта уже есть полная indicator library
или готовая signal/strategy runtime line.
