---
type: system
status: active
confidence: high
stability: archived
updated: 2026-05-20
review_after: null
sources: []
---

# Журнал Базы Знаний

## [2026-05-20] ingest | Karpathy LLM Wiki

Создана структура базы знаний CRYPTOTEHNOLOG по паттерну Karpathy LLM Wiki:

- добавлен immutable raw source note,
- добавлены schema и operating rules,
- добавлены index и append-only log,
- добавлены стартовые concept, workflow, decision и risk pages,
- добавлен health-check script.

## [2026-05-20] automation | CI and source ingest

Добавлен GitHub Actions CI для Rust checks и knowledge-base health checks. Добавлен `scripts/new_source_note.ps1`, который создает raw source notes со stable source IDs, frontmatter, index entries, log entries и immediate health-check validation.

## [2026-05-20] workflow | Codex and Obsidian usage

Задокументировано, как Codex должен читать и обновлять wiki во время engineering work, и как Obsidian используется как Markdown vault interface без превращения в runtime dependency.

## [2026-05-20] automation | Agent rules and pre-commit policy

Добавлен root `AGENTS.md` с правилами для AI agents. Добавлен Git hook installer и задокументировано, что pre-commit knowledge checks должны оставаться fast, local, deterministic и network-free.

## [2026-05-20] automation | Local checks

Добавлена local Markdown link validation и `scripts/check_all.ps1` для fast local check set. Link checker валидирует только local Markdown targets и включен в CI, но не в pre-commit.

## [2026-05-20] automation | Development status

Добавлен `scripts/dev_status.ps1` как read-only session-start diagnostic для Git status, last commit, remotes, CI workflow presence, pre-commit hook presence и core tool versions.

## [2026-05-20] documentation | Russian language policy

Проектная документация переведена на русский язык по варианту B: русский основной текст, английские technical terms сохраняются в скобках или как code/config/API contracts. Language policy добавлена в `AGENTS.md` и `knowledge/schema.md`.

## [2026-05-20] workflow | Obsidian local artifacts

После подключения Obsidian уточнено, что `.obsidian/`, `.canvas`, `.base` и daily notes являются user-specific локальными artifacts. Git игнорирует их, а `kb_health_check.ps1` проверяет только managed knowledge files.

## [2026-05-20] system | Curated knowledge graph

Добавлен `knowledge/graph.md` с curated Mermaid-графом ключевых смысловых связей. Health-check должен проверять наличие `graph.md` и YAML frontmatter, но не валидировать семантику графа.

## [2026-05-20] lifecycle | Stale knowledge warnings

Добавлены `stability` и `review_after` в schema и текущие managed knowledge pages. Добавлен `scripts/kb_stale_check.ps1`, который выдает warning-only уведомления о страницах, требующих review. Также зафиксировано правило: при добавлении новых `decision` или `risk` pages нужно явно проверить, требуется ли обновление `knowledge/graph.md`.

## [2026-05-20] ingest | MVP development sources

Добавлен первый MVP knowledge package: official source notes по Deribit API и Polymarket Gamma/CLOB API, low-confidence source note по Quantum Bot, strategy/risk pages для probability basis, postponed funding carry page, architecture pages для data pipeline и deterministic replay, а также MVP roadmap. `knowledge/graph.md` обновлен только curated связями.

## [2026-05-20] workflow | Coding standards

Добавлена страница `knowledge/wiki/coding-standards.md` как короткий engineering contract. Добавляется compliance check для запрета устаревших Python dependency managers и `pip install` в Dockerfile/scripts. Проверка включается в CI и `scripts/check_all.ps1`, но не в pre-commit.

## [2026-05-20] specs | MVP implementation blockers

Добавлены инженерные specifications для старта API/data coding: `spec-deribit-iv-calculation.md`, `schema-postgres-tables.md`, `example-config-parameters.md`, `rust-events-contracts.md`. Обновлены `knowledge/index.md` и curated `knowledge/graph.md`.

## [2026-05-20] research | Hermes and OmniRoute boundary

Добавлены source notes и wiki pages для Hermes Agent, OmniRoute и future agent research workflow. Зафиксировано, что Hermes/OmniRoute относятся только к research layer и не могут быть частью deterministic execution path.

## [2026-05-20] contracts | Adapter traits and research boundary

Уточнены proposed Rust adapter traits в `rust-events-contracts.md`: `DeribitDiscoveryAdapter`, `PolymarketDiscoveryAdapter`, `EventJournal`, supporting types и error categories. Добавлена страница `workflow-research-vs-core.md`, фиксирующая границу между research layer и deterministic core.

## [2026-05-20] workflow | Onboarding and research promotion

Добавлена страница `workflow-onboarding.md` для новых разработчиков и AI-сессий. В `workflow-research-vs-core.md` добавлены критерии переноса кода из `research/` в deterministic core.

## [2026-05-20] implementation | Rust contracts and mock adapters

Реализованы Rust contracts в `crates/common`: raw event types, supporting market types, sync discovery traits, mock Deribit/Polymarket adapters и in-memory event journal. Добавлены unit tests для mock adapters, raw preservation, duplicate detection и deterministic replay ordering/filtering.

## [2026-05-20] implementation | Probability basis matcher skeleton

Добавлен `crates/common/src/probability_basis.rs`: deterministic matcher skeleton для mock Deribit/Polymarket data, matched/rejected decisions, rejection reasons, net edge calculation и golden replay fixture test. Probability model пока mock-использует `mark_iv`, финальная Black-Scholes implementation остается следующим слоем.

## [2026-05-20] implementation | Black-Scholes probability model

`crates/common/src/probability_basis.rs` заменил mock probability на Black-Scholes `N(d2)` для call-like события `S_T > K` с MVP assumptions `r=0`, `q=0`. Добавлены tests для zero/negative IV, expired option, deep ITM/OTM behavior и deterministic normal CDF approximation. Добавлен `knowledge/README.md` как короткий вход в базу знаний.

## [2026-05-20] research | LightRAG deferred boundary

Добавлены source notes по HKUDS LightRAG, LightRAG arXiv paper и стороннему LightRAG MCP server. Добавлены `tool-lightrag.md` и `workflow-phase1-research.md`. Зафиксировано решение: LightRAG документируется как preferred research-memory candidate, но установка, Docker wiring, MCP wiring, ingestion данных и agent workflows запрещены до прохождения Phase 0 exit gate.

## [2026-05-20] implementation | Probability basis replay runner

`crates/replay` превращен в Phase 0 probability-basis replay runner: fixed mock `MarketEvent` fixture прогоняется через matcher и выдает reproducible matched/rejected report. Добавлен `config/phase_gate.toml` как machine-readable mirror Phase 0 gate для будущей CI-проверки запретов LightRAG/Docker/MCP до Phase 1.

## [2026-05-20] automation | Fixture replay regression and phase gate check

Probability-basis replay fixture вынесен из hardcoded Rust в `fixtures/probability_basis/golden_events.psv`, а expected output - в `fixtures/probability_basis/golden_report.txt`. Добавлены `scripts/run_replay_regression.ps1` и `scripts/check_phase_gate.ps1`; оба включены в `scripts/check_all.ps1` и GitHub Actions CI.

## [2026-05-20] implementation | Basis observations writer contract

Добавлен `crates/common/src/observations.rs`: Rust-модель `BasisObservation`, conversion из matched `ProbabilityBasisFeature`, `BasisObservationWriter` trait и `InMemoryBasisObservationWriter` без PostgreSQL подключения. Replay runner теперь прогоняет matched decisions через in-memory observation writer. `run_backtest.ps1` остается отложенным до появления PnL/trade model.

## [2026-05-20] implementation | Basis observations storage boundary

Добавлен PostgreSQL-oriented storage boundary без real DB dependency: `BasisObservationRow`, fixed `basis_observations` column order, `BasisObservationRowWriter` trait и `PostgresBasisObservationAdapter` skeleton с stable `INSERT` SQL template. Реальное `sqlx`/`tokio-postgres` подключение остается отдельным будущим шагом.

## [2026-05-20] automation | Golden fixture governance

Replay core вынесен в `crates/replay/src/lib.rs`, а `main.rs` стал тонкой CLI-оберткой. Добавлены `scripts/update_golden_fixture.ps1` и `scripts/check_golden_fixture_current.ps1`; CI теперь проверяет, что перегенерация golden report не оставляет diff. В `spec-deribit-iv-calculation.md` зафиксирована model version `black_scholes_single_strike_v1`.

## [2026-05-20] automation | Pricing model version and script docs

Добавлена Rust-константа `PRICING_MODEL_VERSION = "black_scholes_single_strike_v1"` и metadata line в replay report. `update_golden_fixture.ps1` усилен проверками `cargo`, fixture path и output directory. Добавлена `workflow-scripts.md`, где зафиксировано, что network integration tests не входят в default CI.

## [2026-05-20] implementation | Semantic replay report

Добавлен `ReplayReport` semantic contract в `crates/replay/src/lib.rs`. Replay теперь генерирует primary `golden_report.json` для machine-readable regression и secondary `golden_report.txt` для human-readable CLI output. Скрипты `update_golden_fixture.ps1`, `run_replay_regression.ps1` и `check_golden_fixture_current.ps1` обновлены для проверки обоих форматов.

## [2026-05-20] implementation | Replay summary metrics

Добавлен `ReplaySummary` поверх `ReplayReport`: counts matched/rejected, counts by rejection reason и average/min/max `net_edge_probability` по matched entries. Golden JSON/text reports обновлены через `scripts/update_golden_fixture.ps1`. `fixtures/manifest.toml` осознанно отложен до появления нескольких replay fixture scenarios.

## [2026-05-20] automation | Replay fixture manifest

Добавлен второй replay scenario `probability_basis_edge_below_threshold` и registry `fixtures/manifest.toml`. `scripts/run_replay_regression.ps1`, `scripts/update_golden_fixture.ps1` и `scripts/check_golden_fixture_current.ps1` теперь работают по manifest и прогоняют все listed scenarios, сохраняя JSON как основной semantic comparison contract.

## [2026-05-20] automation | CI golden fixture newline compatibility

После проверки GitHub Actions выявлен риск падения Rust golden JSON test на `windows-latest` из-за различий `CRLF/LF` после checkout. Тест semantic JSON report теперь нормализует newlines перед сравнением, сохраняя строгую проверку содержимого fixture.

## [2026-05-20] automation | CI golden freshness newline compatibility

GitHub Actions подтвердил, что `cargo test` исправлен, но `check_golden_fixture_current.ps1` падал на raw-сравнении golden files до/после regeneration. Freshness check теперь нормализует `CRLF/LF` перед сравнением, чтобы проверять semantic staleness, а не стиль line endings checkout.

## [2026-05-20] automation | Replay manifest helper and CI status

Общий replay manifest parser вынесен в `scripts/lib/replay_manifest.ps1` и подключен из replay regression/update/freshness scripts. `scripts/dev_status.ps1` теперь best-effort показывает latest GitHub Actions status для `main` через GitHub API, не падая при отсутствии сети, rate limit или недоступном API.

## [2026-05-20] automation | Invalid quote replay fixture and CI warning

Добавлен replay scenario `probability_basis_invalid_quote`, покрывающий data-quality rejection path `InvalidQuote`. `scripts/dev_status.ps1` теперь выводит короткий warning, если latest GitHub Actions status для `main` отличается от `completed/success`.

## [2026-05-20] automation | Expiry mismatch replay fixture

Добавлен replay scenario `probability_basis_expiry_mismatch`, покрывающий temporal/event alignment rejection path `ExpiryMismatch`. В `arch-deterministic-replay.md` добавлена короткая таблица replay scenarios и список rejection paths, которые еще не покрыты отдельными fixtures.

## [2026-05-20] automation | Replay manifest validation

В `scripts/lib/replay_manifest.ps1` добавлена parser-level validation: scenario names должны быть уникальны, а `fixture`/`expected_json`/`expected_text` paths не должны дублироваться. Добавлен `scripts/check_replay_manifest.ps1`, включенный в `scripts/check_all.ps1` и GitHub Actions до replay regression.

## [2026-05-20] governance | Phase 0 model and live ingestion rules

Зафиксированы governance rules: JSON является обязательным Phase 0 report contract; изменение `PRICING_MODEL_VERSION` требует обновления replay golden reports в том же commit/PR; Phase 0 exit gate включает 7-day live ingestion soak test на реальных Deribit/Polymarket data без live trading; PowerShell scripts остаются developer tooling и не должны быть runtime loop для live monitoring. Добавлен `scripts/check_pricing_model_fixture_update.ps1` в `check_all` и CI.

## [2026-05-20] implementation | Read-only ingestion skeleton

Добавлен `crates/ingestion` как Phase 0 read-only ingestion boundary: `IngestionConfig`, `IngestionErrorKind`, `IngestionClient`, `MockIngestionClient`, `LiveIngestionClient` stub и `ingest_once()` helper, который пишет raw events до normalized events. Добавлен fixture `fixtures/ingestion/api_error_reconnect_sequence.psv` для API error -> reconnect -> recovered batch scenario.

## [2026-05-20] implementation | Ingestion to replay orchestration test

Добавлен fixture `fixtures/ingestion/happy_path_batches.psv` и thin orchestration test: Deribit mock batch + Polymarket mock batch пишутся в `EventJournal`, затем читаются через replay filter, проходят `match_from_market_events()` и превращаются в `BasisObservation`. Тест остается полностью deterministic: без сети, реальных API, PostgreSQL подключения и trading side effects.

## [2026-05-20] implementation | Negative ingestion orchestration fixture

Добавлен fixture `fixtures/ingestion/malformed_polymarket_quote.psv`: raw Polymarket event сохраняется в `EventJournal`, но malformed normalized quote получает `InvalidQuote` в probability-basis matcher и не создает `BasisObservation`. Добавлен lightweight `fixtures/ingestion/manifest.toml` и parser-level validation для ingestion orchestration scenarios.

## [2026-05-20] automation | Ingestion manifest check

Добавлен `scripts/check_ingestion_manifest.ps1`, включенный в `scripts/check_all.ps1` и GitHub Actions. Replay и ingestion manifest wrappers теперь используют общий lightweight helper `scripts/lib/manifest_utils.ps1` для TOML subset parsing, uniqueness checks и path normalization без запуска `cargo`.

## [2026-05-20] implementation | Normalized batch validator and fixture path check

Добавлен `NormalizedBatchValidator` contract в `crates/ingestion`: `ingest_once_with_validator()` сохраняет raw events до validation, но пишет normalized events только после успешной проверки. `Phase0NormalizedBatchValidator` покрывает базовые identity/value/timestamp sanity checks. Добавлен общий `scripts/check_fixture_paths.ps1`, подключенный к `scripts/check_all.ps1` и CI для проверки paths из replay и ingestion manifests.

## [2026-05-20] implementation | Ingestion validation report

Добавлен `ValidationReport` и `ingest_once_with_report()` для ingestion soak telemetry: raw events сохраняются, accepted normalized events пишутся, rejected normalized events остаются в structured report с counters и причинами. `fixtures/ingestion/manifest.toml` расширен semantic expectations: `expected_raw_events`, `expected_normalized_events`, `expected_validation_errors` и `expected_observations`.

## [2026-05-20] implementation | Ingestion semantic reports

Добавлен `IngestionReport` поверх одного или нескольких `ValidationReport`: totals, counts by source и counts by rejection message. Добавлены semantic golden reports `fixtures/ingestion/happy_path_report.json` и `fixtures/ingestion/malformed_polymarket_quote_report.json`; `fixtures/ingestion/manifest.toml` теперь содержит `expected_report`.

## [2026-05-20] implementation | Deribit live ingestion skeleton

Добавлен `DeribitLiveIngestionClient` без network calls в default path: URL construction для `public/ticker`, parsing boundary на fixture payload `fixtures/ingestion/deribit_ticker_eth_3000_call.json`, raw + normalized Deribit batch output и explicit `NotImplemented` для `poll_once()`. Добавлен Rust binary `render_ingestion_report` и `scripts/update_ingestion_golden.ps1` для явной регенерации ingestion semantic golden reports.

## [2026-05-20] implementation | Polymarket live ingestion skeleton

Добавлен `PolymarketLiveIngestionClient` без network calls в default path: Gamma market URL construction, parsing boundary на fixture payload `fixtures/ingestion/polymarket_gamma_eth_above_3000.json`, raw + normalized Polymarket batch output и explicit `NotImplemented` для `poll_once()`. Добавлен `scripts/check_ingestion_golden_current.ps1`, включенный в `scripts/check_all.ps1` и GitHub Actions, чтобы ingestion semantic golden reports не устаревали незаметно.

## [2026-05-20] refactor | Live adapter fixture parsing and ingestion regression

Добавлен общий `JsonFixtureParser` для fixture parsing boundary в Deribit/Polymarket live adapter skeletons без новых dependencies и без network calls. Добавлен `scripts/run_ingestion_regression.ps1`, включенный в `scripts/check_all.ps1` и GitHub Actions, чтобы semantic ingestion reports проверялись через CLI/script contract, а не только Rust unit tests.

## [2026-05-20] implementation | Live HTTP transport boundary

Добавлен `LiveHttpTransport` boundary `GET url -> payload_json`, `DisabledHttpTransport` как default no-network transport и `FixtureHttpTransport` для deterministic tests. Deribit/Polymarket live skeletons теперь могут получать fixture payloads через transport boundary и превращать их в `IngestionBatch` без реальной сети.

## [2026-05-20] implementation | Feature-gated network transport

Добавлен optional `ReqwestHttpTransport` за Cargo feature `network-integration` и ручной `network_connectivity_check` binary для read-only Deribit/Polymarket connectivity checks. Добавлен `scripts/run_network_connectivity_check.ps1` и manual GitHub Actions workflow `Network integration`; default CI и `check_all` остаются offline.

## [2026-05-20] implementation | Live ingestion probe report

Добавлен `LiveIngestionProbeReport` для ручного network connectivity check: endpoint, URL, status, payload bytes, latency_ms, error kind и error message. `scripts/run_network_connectivity_check.ps1` сохраняет JSON report в `artifacts/network_connectivity_report.json`, а manual GitHub Actions workflow загружает его как artifact.

## [2026-05-20] automation | Network report history

`scripts/run_network_connectivity_check.ps1` получил параметры `-OutputPath` и `-Timestamped`, чтобы локальные network reports можно было сохранять историей. Добавлен `scripts/summarize_network_reports.ps1`, который агрегирует JSON reports по endpoint и показывает ok/error counts, error rate, latency stats и latency delta. `artifacts/` добавлен в `.gitignore`.

## [2026-05-20] implementation | Live probe replay

Добавлен ручной Phase 0 vertical slice `live_probe_replay`: feature-gated Rust binary делает read-only HTTP probe, пытается распарсить Deribit/Polymarket payloads, сохраняет raw/normalized events только в `InMemoryEventJournal`, запускает probability-basis matcher и выводит `live_probe_replay_report.json`. Добавлен `scripts/run_live_probe_replay.ps1` с `-OutputPath`/`-Timestamped`; manual `Network integration` workflow теперь загружает `live-probe-replay-report` artifact рядом с connectivity report. Default CI, `check_all`, PostgreSQL и trading path не затронуты.

## [2026-05-20] implementation | Real-shaped REST payload parsing

Ingestion parsing boundary переведен с string-based fixture extraction на `JsonPayloadParser` поверх `serde_json`. Deribit parser теперь поддерживает JSON-RPC `result.*` и short option expiry формат вроде `ETH-1JUN26-3000-C`; Polymarket Gamma parser поддерживает `slug`, JSON-encoded `outcomes`/`outcomePrices`, string/number liquidity и Phase 0 fallback `bid=ask=outcomePrice` до подключения CLOB spread/depth. Добавлен `scripts/summarize_live_probe_replay_reports.ps1` для агрегации parse success/error rate и matcher readiness по manual reports.

## [2026-05-20] implementation | Deribit option discovery for live probe

Добавлен read-only discovery boundary для Deribit option instruments: `DeribitOptionDiscoveryCriteria`, `DeribitDiscoveredOption`, `public/get_instruments` URL construction и выбор ближайшего ETH call candidate перед ticker polling. `live_probe_replay` теперь делает `discover candidate option -> ticker -> normalize -> matcher` вместо hardcoded `ETH-1JUN26-3000-C`. Manual report получил `payload_shape_versions`, чтобы видеть parser contract для instruments, ticker и Polymarket Gamma payloads.

## [2026-05-20] implementation | Polymarket market discovery for live probe

Добавлен read-only discovery boundary для Polymarket Gamma markets: `PolymarketMarketDiscoveryCriteria`, `PolymarketDiscoveredMarket`, Gamma markets URL construction и deterministic selection по required terms, outcome, active/closed state и liquidity. `live_probe_replay` теперь делает Polymarket `discover market candidate -> market-by-slug -> normalize -> matcher` вместо hardcoded `eth-above-3000-june-1`. Report расширен `selection_report`: selected Deribit instrument, target/selected expiry, strike distance и selected Polymarket market/event/liquidity.

## [2026-05-20] automation | Live probe replay summary selection warnings

`scripts/summarize_live_probe_replay_reports.ps1` теперь выводит выбранную Deribit/Polymarket пару отдельной таблицей `Selected Candidates`, выносит payload shape versions из основной summary-строки и показывает warning, если `strike_distance > 0` или `selected_expiry_ts_ms != target_expiry_ts_ms`. Это делает basis mismatch risk заметным в manual report summary до перехода к более глубокой live ingestion telemetry.

## [2026-05-20] implementation | Live probe replay expiry dates

`live_probe_replay_report.json` расширен человекочитаемыми UTC fields `target_expiry_date` и `selected_expiry_date` рядом с машинными `target_expiry_ts_ms` и `selected_expiry_ts_ms`. `scripts/summarize_live_probe_replay_reports.ps1` теперь показывает expiry mismatch warnings через даты, чтобы manual Phase 0 reports читались без ручного перевода Unix milliseconds.

## [2026-05-20] implementation | Live probe replay mismatch flags

`selection_report` в `live_probe_replay_report.json` расширен derived flags `strike_mismatch` и `expiry_mismatch`. `scripts/summarize_live_probe_replay_reports.ps1` теперь использует эти machine-readable flags для warnings и сохраняет fallback-расчет для старых reports без новых полей.

## [2026-05-20] implementation | Live probe replay selection quality

`selection_report` получил derived field `selection_quality` со значениями `missing`, `exact`, `nearby` и `mismatch`. `scripts/summarize_live_probe_replay_reports.ps1` показывает этот статус в таблице `Selected Candidates` и fallback-считает его для старых reports без нового поля.

## [2026-05-20] hardening | Serde live probe replay report

`live_probe_replay_report.json` переведен с ручной строковой сборки на локальные `serde Serialize` DTO в `crates/ingestion/src/bin/live_probe_replay.rs`. Добавлен feature-gated тест, который сериализует report и парсит его обратно через `serde_json`, включая diagnostic message с кавычками и newline. В `coding-standards.md` добавлено правило: machine-readable JSON contracts должны формироваться через typed DTO и `serde Serialize`.

## [2026-05-20] hardening | Phase 0 normalized event validation

`Phase0NormalizedBatchValidator` теперь отклоняет normalized events с unsupported `schema_version` и с `received_ts_ms < exchange_ts_ms`, сохраняя raw events в journal. Добавлен ingestion scenario `schema_timestamp_invalid_batches` и semantic report `schema_timestamp_invalid_report.json`, чтобы regression показывал data-quality rejection до попадания события в matcher.

## [2026-05-20] hardening | Polymarket parser error propagation

В `PolymarketLiveIngestionClient::parse_gamma_market_payload()` удален production-style `expect("checked above")`; missing outcome и несогласованные `outcomes`/`outcomePrices` теперь возвращают явный `IngestionError`. Добавлены targeted tests на Gamma payload без `outcomes` и с коротким `outcomePrices`, чтобы external payload shape не мог вызвать panic в parser boundary.

## [2026-05-20] hardening | Replay serde, pricing assumptions, observation metadata

`ReplayReport` JSON переведен на typed `serde Serialize` contract вместо ручной сборки строк. Добавлен `rust-toolchain.toml` для фиксации stable Rust channel при `rust-version = 1.93`. Black-Scholes assumptions (`risk_free_rate`, `dividend_yield`, `milliseconds_per_year`) вынесены в `ProbabilityBasisConfig`. `basis_observations` row/SQL contract расширен полями `schema_version` и `config_version`.

## [2026-05-20] hardening | Timestamp semantics and JSON writer guard

`PolymarketOutcomeQuote` получил отдельное поле `target_expiry_ts_ms`, чтобы не смешивать quote timestamp (`meta.exchange_ts_ms`) и event/settlement target timestamp. Probability-basis matcher теперь использует `target_expiry_ts_ms` для expiry matching и `max_quote_time_skew_ms` для rejection `StalePair`. Добавлен CI/local script `check_manual_json_writers.ps1`, который запрещает новые ручные JSON writers в `crates/replay`.

## [2026-05-20] source | Rust Skills

Изучен GitHub repository `leonardomso/rust-skills`. Добавлен source note `knowledge/raw/sources/source-rust-skills.md`. Вывод: полезно как optional Codex skill для Rust review/type-safety/error-handling, но не должно заменять project-specific `AGENTS.md`.

## [2026-05-20] workflow | Phase 0 daily report

Добавлен `scripts/run_phase0_daily_report.ps1`, который локально агрегирует replay reports, ingestion reports и последние probe artifacts в `artifacts/phase0_daily_report.json` и `.md` без LLM, сети, PostgreSQL и trading.

## [2026-05-20] hardening | Feature-gated PostgreSQL writer skeleton

Добавлен feature flag `postgres-writer` в `crates/common`. `PostgresEventJournalWriter` фиксирует future writer API для `event_journal`, но без real DB connector: default build не зависит от PostgreSQL crates, а feature-gated writer возвращает `JournalErrorKind::Storage`.

## [2026-05-20] policy | Rust Skills advisory use

В `AGENTS.md` зафиксировано, что локальный `rust-skills` можно использовать как advisory review skill для Rust-кода, но project-specific правила CRYPTOTEHNOLOG из `AGENTS.md` и `knowledge/` имеют приоритет.

## [2026-05-20] implementation | Ingestion to journal row vertical slice

`InMemoryEventJournal` теперь сохраняет append-order `EventJournalRow` snapshots для raw и normalized events. Ingestion fixture transport test проверяет полный offline путь: fixture HTTP payload -> raw event -> normalized event -> journal row -> replay matcher -> `BasisObservation`.

## [2026-05-20] implementation | EventJournalRowWriter test sink and dev status advisory skill

Добавлен `InMemoryEventJournalRowWriter` как тестовый sink для `EventJournalRowWriter`, чтобы ingestion мог зеркалировать raw и accepted normalized events в future storage-row boundary без PostgreSQL connector. `scripts/dev_status.ps1` теперь показывает наличие optional `rust-skills` advisory review tool.

## [2026-05-21] hardening | EventJournalRowWriter failure path

Добавлен negative test с failing `EventJournalRowWriter`: storage-row failure теперь явно возвращается из ingestion как `IngestionErrorKind::JournalWrite`, без panic. Тест фиксирует, что raw event уже сохранен в `EventJournal`, но normalized event не пишется после сбоя row-writer mirror.

## [2026-05-21] hardening | BasisObservationRowWriter failure path

Добавлен helper `write_basis_observation_rows()` и negative test с failing `BasisObservationRowWriter`. Derived `BasisObservation` теперь проходит через row boundary, а storage failure возвращается как `ObservationWriteErrorKind::Storage`, без panic и без silent drop.

## [2026-05-21] implementation | BasisObservationRowWriter offline success path

Добавлен `InMemoryBasisObservationRowWriter` и integration test: ingestion -> matcher -> `BasisObservation` -> `BasisObservationRowWriter`. Это закрывает полный offline путь до будущей таблицы `basis_observations` без PostgreSQL connector, сети или trading side effects.

## [2026-05-21] implementation | Phase 0 pipeline report

Добавлен `Phase0PipelineReport` в `crates/ingestion`: typed `serde Serialize` report contract с counts по offline vertical slice этапам: raw events, normalized events, journal rows, match decisions, observations и observation rows. Добавлен тест JSON serialization/parsing для этого report.

## [2026-05-21] implementation | Phase 0 pipeline report CLI wrapper

Добавлен Rust binary `render_phase0_pipeline_report` и script wrapper `scripts/run_phase0_pipeline_report.ps1`. Они генерируют `artifacts/phase0_pipeline_report.json` из `fixtures/ingestion/happy_path_batches.psv` через offline vertical slice без сети, PostgreSQL и trading.

## [2026-05-21] implementation | Phase 0 pipeline golden freshness

Добавлен golden/freshness слой для `Phase0PipelineReport`: `fixtures/phase0_pipeline/golden_report.json`, `scripts/update_phase0_pipeline_golden.ps1`, `scripts/check_phase0_pipeline_golden_current.ps1`. Проверка включена в `scripts/check_all.ps1` и CI, чтобы offline vertical slice report был таким же проверяемым контрактом, как replay и ingestion reports.

## [2026-05-21] implementation | Phase 0 pipeline semantic regression

Добавлен Rust-level semantic regression test для `Phase0PipelineReport`: тест читает `fixtures/phase0_pipeline/golden_report.json`, десериализует его в typed DTO и сравнивает с текущим deterministic offline vertical slice report. Это дополняет script-level freshness-check и не зависит от форматирования JSON.

## [2026-05-21] maintenance | dev_status GitHub API diagnostic

Уточнено сообщение `scripts/dev_status.ps1` при недоступности GitHub API: теперь оно явно объясняет, что внутри Codex sandbox API может быть недоступен без отдельного разрешения сети. Обновлена документация `workflow-scripts.md`.

## [2026-05-21] implementation | Phase 0 pipeline manifest scenarios

Добавлен второй Phase 0 pipeline scenario `invalid_normalized_event_preserves_raw_but_no_observation`: raw Polymarket event сохраняется, invalid normalized quote отклоняется, `BasisObservation` не создается. Phase 0 pipeline reports переведены на `fixtures/phase0_pipeline/manifest.toml`, добавлены manifest check, manifest-driven regression runner и freshness-check по всем expected reports.

## [2026-05-21] implementation | Phase 0 pipeline storage writer failure scenario

`Phase0PipelineReport` расширен полями `status`, `error_stage`, `error_message`, чтобы controlled storage failures не маскировались под нулевые counts. Добавлен сценарий `storage_writer_failure_preserves_reported_failure`, где pipeline доходит до `BasisObservation`, но `BasisObservationRowWriter` возвращает `Storage` error report. В `workflow-scripts.md` добавлена таблица покрытых Phase 0 pipeline paths.

## [2026-05-21] implementation | Phase 0 daily report pipeline status summary

`scripts/run_phase0_daily_report.ps1` теперь агрегирует Phase 0 pipeline reports из `fixtures/phase0_pipeline/` и показывает status-aware summary: количество `ok`/`error` scenarios, counts по этапам pipeline и `error_stage` для controlled failures. Обновлена документация `workflow-scripts.md`.

## [2026-05-21] implementation | Event journal read persistence boundary

Добавлен read-only storage-row boundary для `event_journal`: `EventJournalReplayQuery`, `EventJournalRowReader`, `InMemoryEventJournalRowReader` и helper `read_market_events_for_replay_from_rows()`. `PostgresEventJournalAdapter` теперь фиксирует future replay `SELECT` contract без real DB connector. Manual `Network integration` workflow дополнен artifact `phase0-daily-report`.

## [2026-05-21] hardening | Postgres event journal reader skeleton and daily report warnings

Добавлен feature-gated `PostgresEventJournalReader` skeleton с `connection_label`, `select_replay_sql()` и controlled `JournalErrorKind::Storage` без реального PostgreSQL connector. `scripts/run_phase0_daily_report.ps1` теперь добавляет warning, если Phase 0 pipeline reports содержат scenarios со статусом не `ok`.

## [2026-05-21] hardening | Executable edge and audit backlog

Probability-basis matcher переведен с decisive midpoint edge на executable-side edge: `gross_mid_edge_probability` остается диагностикой, а threshold применяется к `gross_executable_edge_probability` после costs. Добавлен replay scenario `probability_basis_mid_edge_false_positive`, где midpoint выглядит привлекательным, но ask-side execution уничтожает edge. `rust-toolchain.toml` зафиксирован на `1.93.0`; отложенные audit items записаны в `roadmap-mvp.md`.

## [2026-05-21] hardening | Deribit instrument parser and midpoint false-positive report check

Добавлен typed `DeribitInstrumentName` parser на discovery/ticker boundary для форматов `ETH-1JUN26-3000-C` и `ETH-20260601-3000-C` без распространения newtype на весь проект. `ReplaySummary` расширен `midpoint_false_positive_count`, matcher возвращает `MidEdgeFalsePositive` для pairs, где midpoint edge прошел бы threshold, но executable pricing нет. Добавлен `scripts/check_midpoint_false_positive_report.ps1`, включенный в `check_all` и CI.

## [2026-05-21] hardening | Replay edge quality summary

`ReplaySummary` расширен блоком `edge_quality` с `matched_count`, `edge_below_threshold_count` и `midpoint_false_positive_count`. `scripts/run_phase0_daily_report.ps1` теперь показывает replay edge quality в JSON/Markdown daily report. Добавлен ручной diagnostic script `scripts/summarize_replay_edge_quality_reports.ps1` для trend-summary midpoint false positives по нескольким replay JSON reports.

## [2026-05-21] hardening | Live probe replay edge quality artifact

`live_probe_replay_report.json` расширен `replay_summary.edge_quality`, чтобы manual live payload probe показывал matched, `EdgeBelowThreshold` и `MidEdgeFalsePositive` counters. `scripts/summarize_live_probe_replay_reports.ps1` теперь выводит edge quality totals, а manual `network-integration` workflow сохраняет `artifacts/live_probe_replay_trend_summary.txt` рядом с live probe JSON artifact.

## [2026-05-21] hardening | Daily report live probe review

`scripts/run_phase0_daily_report.ps1` теперь подхватывает optional `artifacts/live_probe_replay_report*.json` и `artifacts/live_probe_replay_trend_summary.txt`, добавляет секцию `Live Probe Review` в Markdown и machine-readable `live_probe_review` в JSON. Daily report добавляет warning, если live probe midpoint false positives превышают matched opportunities.

## [2026-05-21] workflow | Manual network artifact readability

Manual `Network integration` workflow теперь загружает `artifacts/live_probe_replay_trend_summary.txt` отдельным artifact `live-probe-replay-trend-summary`, чтобы trend-summary можно было открыть без распаковки общего live probe JSON artifact. В `workflow-scripts.md` добавлена короткая секция “как читать manual network artifacts”.

## [2026-05-21] implementation | Polymarket CLOB executable price boundary

Добавлен read-only CLOB orderbook parser boundary для Polymarket: `PolymarketClobBookQuote`, CLOB `/book?token_id=...` URL helper, payload shape `polymarket_clob_book_v1` и fixture flow `Gamma market + CLOB book -> executable bid/ask`. Gamma `outcomePrices` остаются fallback для discovery/probe, а CLOB best bid/ask теперь показывает, где появляется реальный executable spread. Добавлены fixtures `polymarket_gamma_eth_above_3000_with_clob_token.json` и `polymarket_clob_book_eth_above_3000_yes.json` плюс unit tests без network calls.

## [2026-05-21] implementation | Live probe CLOB executable pricing

Manual `live_probe_replay` подключен к Polymarket CLOB boundary: после Gamma discovery он извлекает `clobTokenIds`, делает read-only CLOB `/book` запрос, нормализует executable bid/ask из orderbook и только затем отправляет Polymarket quote в matcher. `live_probe_replay_report.json` получил `warnings[]`; если CLOB spread превышает `0.10`, добавляется warning `WideExecutableSpread`. Default CI и `check_all` остаются offline.

## [2026-05-21] workflow | Live probe warning summary

`scripts/summarize_live_probe_replay_reports.ps1` теперь выводит общее количество warnings и агрегированный список warning kinds, чтобы `WideExecutableSpread` был виден в trend-summary без открытия JSON artifact.

## [2026-05-21] implementation | Polymarket Gamma discovery diagnostics

Manual `live_probe_replay` теперь добавляет `polymarket_discovery_diagnostics` в JSON report: top Gamma candidates, missing search terms, outcome availability, liquidity check, `active`/`closed` flags и rejection reasons. `scripts/summarize_live_probe_replay_reports.ps1` выводит этот блок в trend-summary. Первый локальный manual probe показал, что blocker находится до CLOB: текущий Gamma `markets` discovery получает нерелевантные активные рынки и не выбирает ETH/3000 candidate, поэтому CLOB `/book` не вызывается.

## [2026-05-21] implementation | Targeted Polymarket Gamma discovery

Polymarket discovery в manual `live_probe_replay` переведен с broad first-page `/markets` на targeted sequence: `public-search?q=eth+3000`, `public-search?q=ethereum+3000`, затем broad `/markets` fallback. Parser discovery payload теперь принимает `markets`, `data/result` и nested `events[].markets` shapes. Добавлен warning `BroadPolymarketGammaDiscovery`, если top candidates отвергнуты только по `terms_mismatch`. Локальный manual probe подтвердил, что pipeline теперь выбирает `will-ethereum-reach-3000-in-may-2026`, доходит до Gamma market, CLOB `/book`, normalized events и matcher без секретов и без trading.
