---
type: workflow
status: active
confidence: high
stability: volatile
updated: 2026-05-20
review_after: 2026-06-19
sources:
  - project-review-2026-05-19
---

# Workflow: Scripts

Эта страница кратко описывает project scripts. Скрипты являются developer tooling, а не runtime dependency deterministic core.

PowerShell scripts допустимы как Phase 0 developer tooling и CI glue. Они не должны становиться runtime loop для live monitoring, ingestion или trading services.

Live monitoring должен быть Rust service/binary. PowerShell может быть только тонким wrapper для запуска такого binary.

## Local Checks

### `scripts/check_all.ps1`

Запускает быстрый локальный набор проверок:

- knowledge health check,
- local Markdown links,
- stale warnings,
- compliance,
- phase gate,
- replay manifest,
- ingestion manifest,
- fixture paths,
- pricing model fixture policy,
- `cargo fmt --check`,
- `cargo check`,
- `cargo test`,
- replay regression,
- ingestion regression,
- golden fixture freshness,
- ingestion golden report freshness.

Использовать перед коммитом.

### `scripts/dev_status.ps1`

Показывает состояние рабочей сессии: Git status, последний коммит, remote, наличие GitHub Actions workflow, latest GitHub Actions status для `main` если GitHub API доступен, наличие hook и версии Rust/UV/Git.

GitHub Actions status читается best-effort через публичный GitHub API. Для public repository токен обычно не нужен. Если API недоступен, rate-limited или repository станет private, можно задать `GITHUB_TOKEN` с минимальными read-only правами на repository metadata/actions. Токен нельзя сохранять в репозитории или wiki.

Если latest GitHub Actions status не `completed/success`, `dev_status` выводит короткий `WARNING`, чтобы красный `main` был заметен в начале рабочей сессии.

## Knowledge Base

### `scripts/kb_health_check.ps1`

Проверяет managed knowledge Markdown files: наличие frontmatter, обязательные страницы и basic structure. Скрипт должен оставаться быстрым, локальным, без сети и без LLM.

### `scripts/kb_stale_check.ps1`

Warning-only проверка `stability` и `review_after`.

### `scripts/validate_local_links.ps1`

Проверяет только локальные Markdown-ссылки. Внешние URL намеренно не проверяются в pre-commit/default local checks.

### `scripts/new_source_note.ps1`

Создает raw source note template и помогает поддерживать source ingestion workflow.

## Git Hooks

### `scripts/install_hooks.ps1`

Устанавливает быстрый pre-commit hook. Hook не должен запускать network checks, LLM calls или heavy audits.

## Replay And Fixtures

### `scripts/run_replay_regression.ps1`

Читает `fixtures/manifest.toml` и запускает `cryptotehnolog-replay` для каждого replay scenario.

Основная проверка сравнивает JSON output с `expected_json` из manifest.

Дополнительная smoke-проверка сравнивает text output с `expected_text` из manifest.

JSON/text output включает `ReplaySummary`: counts matched/rejected, counts by rejection reason и агрегаты `net_edge_probability` по matched entries.

Это smoke-level CLI regression, а не замена Rust unit tests.

Manifest parsing находится в `scripts/lib/replay_manifest.ps1`, чтобы `run_replay_regression.ps1`, `update_golden_fixture.ps1` и `check_golden_fixture_current.ps1` не дублировали один и тот же TOML subset parser.

Общие lightweight helpers для manifest parsing, path normalization и uniqueness checks находятся в `scripts/lib/manifest_utils.ps1`. Они используются replay и ingestion manifest wrappers, но не являются полноценным TOML parser.

### `scripts/check_replay_manifest.ps1`

Проверяет `fixtures/manifest.toml` без запуска `cargo`:

- scenario names должны быть уникальны,
- `fixture`, `expected_json` и `expected_text` paths не должны дублироваться,
- referenced fixture/report files должны существовать.

Включен в `check_all` и CI до replay regression, чтобы ошибки manifest ловились быстро.

### `scripts/check_ingestion_manifest.ps1`

Проверяет `fixtures/ingestion/manifest.toml` без запуска `cargo`:

- scenario names должны быть уникальны,
- `fixture` и `expected_report` paths не должны дублироваться,
- referenced fixture files должны существовать,
- `expected_observations`, `expected_raw_events`, `expected_normalized_events` и `expected_validation_errors` должны быть числами.

Включен в `check_all` и CI, чтобы ingestion orchestration fixtures оставались видимым контрактом, а не только Rust unit-test detail.

### `scripts/run_ingestion_regression.ps1`

Читает `fixtures/ingestion/manifest.toml` и запускает Rust binary `render_ingestion_report` для каждого ingestion scenario.

Основная проверка сравнивает generated JSON report с `expected_report` из manifest. Это script/CLI-level semantic regression, а не замена Rust unit tests.

Включен в `check_all` и CI до freshness-check.

### `scripts/check_fixture_paths.ps1`

Проверяет существование файлов, на которые ссылаются все текущие fixture manifests:

- replay `fixture`, `expected_json`, `expected_text`,
- ingestion `fixture`, `expected_report`.

Скрипт использует те же manifest wrappers и общий `scripts/lib/manifest_utils.ps1`. Он отделяет проверку путей от проверки структуры manifest, чтобы новые типы fixtures могли подключаться к одному path-existence check.

### `scripts/check_pricing_model_fixture_update.ps1`

Проверяет governance rule для `PRICING_MODEL_VERSION`.

Если в diff изменена строка `PRICING_MODEL_VERSION` в `crates/common/src/probability_basis.rs`, то в том же diff должны быть обновлены replay golden reports в `fixtures/probability_basis/`.

Скрипт включен в `check_all` и CI.

### `scripts/update_golden_fixture.ps1`

Перегенерирует:

- все `expected_json` reports из `fixtures/manifest.toml`,
- все `expected_text` reports из `fixtures/manifest.toml`.

Использовать только когда изменение matcher/pricing/replay behavior ожидаемо. Изменение golden report должно быть reviewable в том же commit/PR.

### `scripts/check_golden_fixture_current.ps1`

Запускает `update_golden_fixture.ps1` и падает, если после перегенерации меняется JSON или text golden report. Включен в `check_all` и CI.

### `scripts/update_ingestion_golden.ps1`

Перегенерирует `expected_report` для всех scenarios из `fixtures/ingestion/manifest.toml`.

Скрипт вызывает Rust binary `render_ingestion_report`, чтобы semantic source of truth оставался в `crates/ingestion`, а не в PowerShell.

Использовать только когда изменение ingestion telemetry/report behavior ожидаемо. Изменение ingestion golden report должно быть reviewable в том же commit/PR.

### `scripts/check_ingestion_golden_current.ps1`

Запускает `update_ingestion_golden.ps1` и падает, если после перегенерации меняется любой `expected_report` из `fixtures/ingestion/manifest.toml`.

Включен в `check_all` и CI. Это freshness-check для ingestion semantic reports, аналогичный replay golden freshness.

## Phase Gate

### `scripts/check_phase_gate.ps1`

Читает `config/phase_gate.toml`. Пока `phase_1_research_enabled = false`, запрещает tracked LightRAG/MCP wiring вне разрешенной документации.

## Compliance

### `scripts/check_compliance.ps1`

Проверяет объективные repository rules: отсутствие deprecated Python dependency files и запрет `pip install` в Dockerfile/scripts.

## Network Integration Tests

Default CI не должен делать реальные запросы к Deribit, Polymarket или другим внешним API.

Future network integration tests должны запускаться только:

- вручную,
- по отдельному CI workflow,
- с явным environment flag,
- с отдельными secrets/rate-limit правилами.

### `scripts/run_network_connectivity_check.ps1`

Ручной read-only network check для Deribit и Polymarket Gamma.

Скрипт запускает Rust binary `network_connectivity_check` с feature `network-integration`, который использует `ReqwestHttpTransport` и делает только публичные GET-запросы:

- Deribit `public/ticker`;
- Polymarket Gamma `markets/slug`.

Скрипт не входит в `check_all`, pre-commit или default CI. Он не использует secrets, не пишет в `event_journal`, не рассчитывает signals и не размещает orders.

По умолчанию результат сохраняется в `artifacts/network_connectivity_report.json`. Для локальной истории можно использовать `-Timestamped`, тогда файл будет сохранен как `artifacts/network_connectivity_report_YYYYMMDD_HHMMSS.json`. Для явного пути использовать `-OutputPath <path>`.

Формат отчёта - JSON-массив `LiveIngestionProbeReport` entries:

- `endpoint`,
- `url`,
- `status`,
- `payload_bytes`,
- `latency_ms`,
- `error_kind`,
- `error_message`.

### `scripts/run_live_probe_replay.ps1`

Ручной Phase 0 vertical slice для проверки пригодности live payloads к текущему deterministic pipeline.

Скрипт запускает Rust binary `live_probe_replay` с feature `network-integration`. Binary делает публичные GET-запросы через `ReqwestHttpTransport`, пытается распарсить ответы Deribit и Polymarket, записывает raw/normalized events только в `InMemoryEventJournal`, запускает probability-basis matcher и формирует machine-readable report.

Ограничения:

- не входит в `check_all`, pre-commit или default CI;
- не использует secrets;
- не пишет в PostgreSQL;
- не запускает runtime loop;
- не размещает orders и не выполняет paper/live trading.

Если HTTP endpoint доступен, но payload не соответствует текущему parser contract, отчёт должен явно показать parse error. Это ожидаемый diagnostic outcome на этапе Phase 0, а не повод маскировать проблему.

По умолчанию результат сохраняется в `artifacts/live_probe_replay_report.json`. Для локальной истории можно использовать `-Timestamped`, тогда файл будет сохранен как `artifacts/live_probe_replay_report_YYYYMMDD_HHMMSS.json`. Для явного пути использовать `-OutputPath <path>`.

Формат отчёта - JSON object:

- `schema_version`,
- `config_version`,
- `pricing_model_version`,
- `probe_reports`,
- `ingestion_report`,
- `replay_summary`,
- `errors`.

### `Network integration` GitHub Actions workflow

Отдельный manual workflow `.github/workflows/network-integration.yml` с `workflow_dispatch`.

Его нужно запускать вручную, когда требуется проверить внешнюю connectivity. Он намеренно отделен от default CI, чтобы обычные PR/push checks оставались deterministic и offline.

Workflow запускает script с `-Timestamped` и загружает `artifacts/network_connectivity_report*.json` как GitHub Actions artifact `network-connectivity-report` даже при failed connectivity check, чтобы можно было видеть endpoint-level причину сбоя.

Workflow также запускает `scripts/run_live_probe_replay.ps1 -Timestamped` и загружает `artifacts/live_probe_replay_report*.json` как artifact `live-probe-replay-report`. Этот artifact показывает не только доступность API, но и то, дошёл ли payload до parser, validator, in-memory event journal и matcher.

### `scripts/summarize_network_reports.ps1`

Читает один или несколько JSON reports по glob pattern и выводит summary по endpoint:

- количество reports,
- `ok` и `error` counts,
- error rate,
- average/min/max latency,
- delta latency между первым и последним report.

Default pattern: `artifacts\network_connectivity_report*.json`.
