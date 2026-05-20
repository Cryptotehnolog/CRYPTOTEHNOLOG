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

## Local Checks

### `scripts/check_all.ps1`

Запускает быстрый локальный набор проверок:

- knowledge health check,
- local Markdown links,
- stale warnings,
- compliance,
- phase gate,
- `cargo fmt --check`,
- `cargo check`,
- `cargo test`,
- replay regression,
- golden fixture freshness.

Использовать перед коммитом.

### `scripts/dev_status.ps1`

Показывает состояние рабочей сессии: Git status, последний коммит, remote, CI hint, наличие hook и версии Rust/UV/Git.

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

Запускает `cryptotehnolog-replay` на `fixtures/probability_basis/golden_events.psv`.

Основная проверка сравнивает JSON output с `fixtures/probability_basis/golden_report.json`.

Дополнительная smoke-проверка сравнивает text output с `fixtures/probability_basis/golden_report.txt`.

JSON/text output включает `ReplaySummary`: counts matched/rejected, counts by rejection reason и агрегаты `net_edge_probability` по matched entries.

Это smoke-level CLI regression, а не замена Rust unit tests.

Когда появится больше одного replay fixture, regression script должен читать `fixtures/manifest.toml` и прогонять все listed scenarios. Пока fixture один, manifest намеренно не создается.

### `scripts/update_golden_fixture.ps1`

Перегенерирует:

- `fixtures/probability_basis/golden_report.json`,
- `fixtures/probability_basis/golden_report.txt`.

Использовать только когда изменение matcher/pricing/replay behavior ожидаемо. Изменение golden report должно быть reviewable в том же commit/PR.

### `scripts/check_golden_fixture_current.ps1`

Запускает `update_golden_fixture.ps1` и падает, если после перегенерации меняется JSON или text golden report. Включен в `check_all` и CI.

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
