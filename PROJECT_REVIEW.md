# CRYPTOTEHNOLOG - инженерный review

Дата: 2026-05-19

## Главная Позиция

Идея проекта технически интересная, но исходное предложение слишком широкое для MVP и смешивает три разных класса задач:

1. надежная инфраструктура рыночных данных (market-data infrastructure),
2. статистически защищаемое торговое исследование (trading research),
3. AI-assisted post-trade analysis.

Детерминированное ядро (deterministic core) должно идти первым. AI-слой должен оставаться вне scope, пока у системы нет чистых данных, воспроизводимых backtests и paper-trading telemetry. Эта часть исходного плана правильная.

Самые слабые места текущего дизайна - рыночные допущения:

- Доступность и ликвидность BitMEX commodity perpetuals надо проверить до построения системы вокруг XAUtUSDT и BRENTUSDT.
- Funding carry в MVP-версии не является market-neutral, если мы просто short perpetual без реального hedge.
- Deribit-to-Polymarket "probability arbitrage" не является простым арбитражем. Это basis trade между разными settlement definitions, liquidity regimes, margin models, expiries и resolution risk.
- Redis Streams полезны для развязки сервисов, но не должны становиться источником истины (source of truth).
- Rust для каждого детерминированного компонента может замедлить раннее исследование. Rust отлично подходит для execution/risk path, но feature research и backtesting могут быстрее двигаться на Python, пока формулы не стабилизированы.

## Что Я Бы Изменил

### 1. Сузить MVP

Начать с одной стратегии и одной пары exchange/data source.

Рекомендованный MVP:

- Data ingestion для Deribit ETH options и Polymarket crypto markets.
- Нормализованные market snapshots.
- Backtest/event replay.
- Paper execution simulator.
- PostgreSQL event journal.
- Без live orders.
- Без Hermes, LightRAG, OmniRoute.

Причина: probability-arbitrage тезис более уникален, но он же с наибольшей вероятностью сломается из-за market-definition mismatch. Его нужно валидировать до постройки большой execution platform.

Альтернативный MVP:

- Только BitMEX funding ingestion.
- Расчет funding features.
- Paper funding strategy.
- PnL simulation с adverse price movement.

Технически это проще, но edge слабее, если мы не найдем реальный hedge.

### 2. Считать paper trading как event replay плюс live shadow mode

Paper trading, который потребляет только live quotes, недостаточен. Нужен deterministic replay из сохраненных raw events.

Минимальные требования:

- Каждый входящий raw event сохраняется до расчета features.
- Каждый signal, risk decision, simulated fill и portfolio update воспроизводим.
- Strategy outputs должны быть детерминированными для одного и того же input event log и config version.

### 3. Рано добавить schema и contract layer

Не использовать Pydantic как внутреннюю модель, если deterministic core пишется на Rust. Каноническими типами должны быть Rust structs, сериализация на старте через JSON или MessagePack. Позже, если потребуется, можно перейти на Protobuf или FlatBuffers.

Рекомендованные event families:

- `MarketEvent`
- `FeatureEvent`
- `SignalEvent`
- `RiskDecision`
- `OrderIntent`
- `ExecutionReport`
- `PortfolioSnapshot`

Каждый event должен включать:

- `event_id`
- `source`
- `exchange_ts`
- `received_ts`
- `instrument_id`
- `schema_version`
- `config_version`

### 4. Отделить research от production config

Human-approved изменения конфигов должны быть явными, версионированными и auditable.

Добавить:

- `config/strategies.toml`
- `config/risk.toml`
- `config/instruments.toml`
- `config/venues.toml`

AI agents могут писать рекомендации, но не auto-apply config patches.

### 5. Risk engine должен быть шире Kelly

Kelly sizing хрупок, когда edge estimates шумные. В этом проекте оценка edge на старте будет очень шумной.

Для MVP использовать capped fractional sizing:

- fixed notional percentage per strategy,
- hard max position size,
- hard daily loss limit,
- hard max drawdown,
- kill switch,
- per-venue exposure limit,
- stale-data rejection,
- spread/liquidity rejection.

Kelly можно добавить позже как research metric, но не как первый production sizer.

## Критика Стратегий

### Funding Rate Carry

Проблема: если MVP просто short positive-funding perp без hedge, это не carry arbitrage. Это directional short exposure с funding income.

Что нужно добавить:

- hedge instrument discovery,
- basis tracking,
- liquidation/margin simulation,
- borrow/financing assumptions, если есть spot hedge,
- stress test для резких commodity rallies.

Вердикт: допустимо только как маленькая paper strategy или data-collection strategy. Не считать market-neutral.

### Deribit vs Polymarket Probability Trade

Проблема: Deribit options не мапятся чисто на Polymarket binary outcomes.

Ключевые несовпадения:

- European option payoff vs prediction-market binary payout.
- Разные expiry timestamps и settlement sources.
- Path-independent option payoff vs event-specific market wording.
- Implied probability из Black-Scholes зависит от модели.
- Polymarket prices включают liquidity, resolution и capital lockup premia.
- Shorting Polymarket outcomes может быть операционно неэквивалентен продаже probability.
- Short option positions на Deribit создают convex tail risk.

Более правильная формулировка MVP:

Пока не называть это арбитражем. Называть `probability_basis`.

Сначала проверить:

- можно ли программно сопоставлять equivalent events,
- сохраняется ли spread после fees/spreads/slippage,
- есть ли execution size на обеих площадках,
- ведет ли себя mark-to-market PnL ожидаемо.

Вердикт: перспективно как research, опасно как заявленный arbitrage.

## Архитектурная Рекомендация

Предлагаемый начальный stack:

- Rust workspace для deterministic services.
- Python сначала только для notebooks/research/reports.
- PostgreSQL как source of truth.
- Redis Streams как transient bus.
- Docker Compose для local infra.
- Prometheus/Grafana после первого полного event loop.

Начальные Rust crates:

- `crates/common`
- `crates/ingestion`
- `crates/features`
- `crates/strategy`
- `crates/risk`
- `crates/execution`
- `crates/replay`

Начальный Python package:

- `research/`
- `scripts/`

## Ближайший Шаг

Построить узкую основу:

1. scaffold repo,
2. добавить Docker Compose с Postgres и Redis,
3. определить event schemas,
4. определить config files,
5. создать replay-first paper-trading loop с mocked market events,
6. добавить CI/lint/test commands.

Только после этого подключать реальные exchange APIs.

## MVP Решение - 2026-05-19

Выбран первый MVP: Deribit + Polymarket `probability_basis`.

Первая milestone - не торговля. Первая milestone - доказать или опровергнуть, можно ли достаточно чисто сопоставлять event pairs для систематического research:

- equivalent underlying,
- compatible event wording,
- compatible expiry и settlement timestamp,
- sufficient order-book liquidity,
- spread, который переживает estimated costs,
- deterministic replay из сохраненных raw events.

Funding carry отложен. Он остается возможным вторым MVP, но только после определения реального hedge или явной маркировки как directional funding-income exposure.

