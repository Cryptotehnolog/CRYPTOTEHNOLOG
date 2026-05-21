---
type: workflow
status: active
confidence: high
stability: stable
updated: 2026-05-21
review_after: 2026-08-18
sources:
  - project-review-2026-05-19
---

# Coding Standards

Эта страница фиксирует технические стандарты разработки CRYPTOTEHNOLOG. Это короткий engineering contract, а не большой style guide.

## Управление Зависимостями

Python dependencies управляются только через `uv`.

Разрешено:

- `uv add`,
- `uv sync`,
- `uv run`,
- `uv lock`.

`pyproject.toml` является единственным источником metadata Python-проекта. Если появляются реальные Python dependencies, `uv.lock` должен быть закоммичен для reproducibility.

Запрещено:

- `requirements.txt`,
- `setup.py`,
- `Pipfile`,
- `Pipfile.lock`,
- `poetry.lock`,
- `pip install` в Dockerfile и project scripts.

## Линтинг И Форматирование

Python:

- `ruff` для lint/format/import sorting.
- `black`, `isort`, `flake8` отдельно не добавлять без отдельного decision review.

Rust:

- `rustfmt` через `cargo fmt --check`.
- `clippy` добавляется в CI, когда кодовая база станет достаточно содержательной.
- toolchain фиксируется в `rust-toolchain.toml`; `rust-version` в workspace и toolchain channel должны быть согласованы.

## Типизация

Rust типизируется компилятором.

Python:

- production Python package должен постепенно идти к `mypy --strict`;
- `research/` может иметь более мягкие правила, чтобы не тормозить исследование.

## Тестирование

Rust:

- `cargo test`.

Python:

- `pytest`;
- `pytest-asyncio` для async tests, когда появится async Python код.

Async Python code не должен использовать `time.sleep()`. Использовать `asyncio.sleep()`.

## JSON Contracts

Machine-readable reports и external JSON contracts должны формироваться через typed DTO и `serde Serialize`.

Ручная сборка JSON через `format!()` допустима только как временный diagnostic fallback или в тестовых строках, но не как основной путь production/manual report output.

## Docker

Для локальной разработки используется `docker-compose.yml`.

Для будущих application images:

- предпочитать multi-stage builds,
- не запускать production containers от root,
- использовать `uv sync --frozen`, а не `pip install`.

## Git

Основная ветка: `main`.

Для разработки использовать feature branches от `main`. Ветка `dev` не вводится, пока нет отдельного release process.

Коммиты должны быть смысловыми. Conventional Commits можно использовать позже, если появится необходимость.

## Запрещенные Практики

- Глобальные переменные для конфигурации runtime.
- Hardcoded absolute paths.
- `time.sleep()` в async code.
- Bare `except:` без типа исключения.
- Секреты, API keys и exchange credentials в репозитории.

## Compliance

Объективные правила проверяются скриптом `scripts/check_compliance.ps1`.

Этот скрипт включен в CI и `scripts/check_all.ps1`, но не входит в pre-commit hook.
