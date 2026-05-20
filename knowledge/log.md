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
