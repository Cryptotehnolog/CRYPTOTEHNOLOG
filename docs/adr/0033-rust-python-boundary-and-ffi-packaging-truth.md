# Python/Rust boundary и FFI packaging truth

**Дата:** 2026-03-24  
**Статус:** Принято

## Контекст

После closure `P_20 / v1.20.0` проект уже имеет устойчивую мультиязычную архитектуру,
но current mixed-language contour всё ещё содержит interpretation drift вокруг Python/Rust boundary.

Текущая фактическая truth по коду выглядит так:

- production runtime, bootstrap, composition root и phase/domain ownership живут на Python-стороне;
- Rust используется как selected performance/data-plane layer;
- в Rust workspace уже существует `crates/ffi`, который собирает extension module `cryptotechnolog_rust`;
- на Python-стороне уже существует [rust_bridge.py](D:/CRYPTOTEHNOLOG/src/cryptotechnolog/rust_bridge.py),
  который импортирует `cryptotechnolog_rust` при доступности и даёт graceful fallback path;
- [main.py](D:/CRYPTOTEHNOLOG/src/cryptotechnolog/main.py) уже является честным Python-first production entrypoint.

При этом остаются реальные ambiguity points:

- `pyproject.toml` всё ещё содержит старый commented Rust block / TODO, как будто FFI contour ещё не существует;
- нет отдельного ADR, который бы закреплял current practical ownership между:
  - Python runtime/composition layer;
  - Rust performance/data-plane layer;
  - `rust_bridge.py` как Python-facing adapter;
  - `crates/ffi` как low-level FFI capability surface;
- packaging/install truth вокруг `cryptotechnolog_rust` не собрана в один explicit contract.

Без отдельного решения этот contour легко начинает читаться неправильно:

- как будто Python package уже автоматически владеет Rust extension build/install flow;
- как будто весь surface `crates/ffi` автоматически является public Python integration contract;
- как будто Rust становится runtime/composition owner;
- как будто `rust_bridge.py` — временный/случайный compatibility file, а не current authoritative Python-facing boundary.

## Рассмотренные альтернативы

1. Ничего не фиксировать отдельно и продолжать опираться только на ранние multilingual ADR плюс текущий код.
2. Считать `crates/ffi` автоматически authoritative public integration surface и implicit packaging truth для Python package.
3. Зафиксировать current Python/Rust boundary отдельным ADR и синхронизировать packaging wording в `pyproject.toml` с фактической архитектурой.

## Решение

Принят вариант 3.

### 1. Python остаётся runtime / composition owner

- Python является owner-ом:
  - production bootstrap;
  - composition root;
  - domain/runtime foundations;
  - health/readiness/degraded truth;
  - phase-level ownership semantics.
- `main.py` и `bootstrap.py` остаются authoritative production runtime path.
- Rust не становится hidden runtime/composition owner.

### 2. Rust остаётся selected performance / bridge owner

- Rust является owner-ом selected high-performance contours:
  - `eventbus`;
  - `risk-ledger`;
  - `audit-chain`;
  - `execution-core`;
  - `ffi`.
- Это performance/data-plane и bridge territory, а не новый top-level runtime owner.
- Наличие Rust crates не означает автоматического переноса phase/runtime ownership из Python в Rust.

### 3. `rust_bridge.py` является authoritative Python-facing bridge surface

- [rust_bridge.py](D:/CRYPTOTEHNOLOG/src/cryptotechnolog/rust_bridge.py) фиксируется как current authoritative Python-facing integration surface для optional Rust extension.
- Его роль:
  - импортировать `cryptotechnolog_rust`, если extension доступен;
  - давать graceful fallback path на Python-реализацию, если extension недоступен;
  - скрывать direct FFI details от большей части Python codebase.
- Следовательно, `rust_bridge.py` — это не случайный compatibility хвост и не временный placeholder.
- Любой broader public Python integration contract должен либо проходить через этот слой, либо явно нормализоваться отдельным архитектурным шагом.

### 4. `crates/ffi` является low-level FFI capability surface

- `crates/ffi` фиксируется как low-level FFI capability surface.
- Этот crate:
  - собирает extension module `cryptotechnolog_rust`;
  - может предоставлять более широкий PyO3 surface, чем текущий authoritative Python-facing contract;
  - не считается автоматически всем public integration contract проекта.
- Следовательно:
  - наличие low-level PyO3 classes/functions в `crates/ffi` не означает, что весь этот surface уже является official Python integration truth;
  - public/authoritative integration truth проходит через текущую boundary discipline, а не через “всё, что уже можно экспортировать из PyO3”.

### 5. Official integration truth для `cryptotechnolog_rust`

Current official integration truth выглядит так:

- Python package `cryptotechnolog` не auto-build-ит и не auto-install-ит Rust extension через `pyproject.toml`;
- `cryptotechnolog_rust` считается optional extension module, который может быть отдельно собран/установлен из Rust/FFI contour;
- Python codebase взаимодействует с ним через `rust_bridge.py`;
- если extension недоступен, authoritative Python path остаётся работоспособным через graceful fallback.

Это означает:

- текущая packaging truth честно отделяет:
  - Python package metadata;
  - Rust workspace / FFI build contour;
  - Python-facing adapter surface.
- Отдельная unified build/install pipeline для Rust extension может понадобиться позже,
  но это уже не implicit truth текущего проекта и не должно молча подразумеваться.

### 6. Что intentionally не делается этим ADR

Этот ADR не:

- открывает новую product line;
- вводит новую phase numbering line;
- переписывает replay/product/runtime semantics;
- требует немедленного широкого refactor Python/Rust integration;
- объявляет весь `crates/ffi` public Python API;
- вводит maturin/setuptools-rust/другой unified packaging pipeline задним числом.

## Последствия

- **Плюсы:** current mixed-language boundary становится явной и ownership-safe.
- **Плюсы:** `rust_bridge.py` получает чёткий статус authoritative Python-facing adapter layer.
- **Плюсы:** `crates/ffi` перестаёт неявно трактоваться как автоматический public integration contract.
- **Плюсы:** packaging/install wording можно синхронизировать без широкого refactor.
- **Минусы:** future Rust/Python integration expansion теперь потребует отдельной нормализации, а не тихого расползания.
- **Минусы:** текущая truth честно признаёт, что unified auto-build/install path для Rust extension пока не оформлен как authoritative package flow.

## Что становится обязательным после этого ADR

1. Читать Python как owner runtime/composition truth.
2. Читать Rust как selected performance/bridge owner, а не top-level runtime owner.
3. Считать `rust_bridge.py` authoritative Python-facing bridge surface.
4. Считать `crates/ffi` low-level FFI capability surface, а не автоматически весь public integration contract.
5. Не описывать `pyproject.toml` так, будто Rust extension всё ещё “ещё не существует” или уже “полностью встроен” в Python packaging flow, если это не подтверждено current implementation truth.

## Связанные ADR

- Развивает [0001-multilingual-architecture.md](D:/CRYPTOTEHNOLOG/docs/adr/0001-multilingual-architecture.md)
- Развивает [0002-rust-workspace-structure.md](D:/CRYPTOTEHNOLOG/docs/adr/0002-rust-workspace-structure.md)
- Согласуется с [0024-production-alignment-composition-root-and-runtime-truth.md](D:/CRYPTOTEHNOLOG/docs/adr/0024-production-alignment-composition-root-and-runtime-truth.md)
