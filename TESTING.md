# Тесты CRYPTOTEHNOLOG

Документация всех тестов проекта. При добавлении новых тестов — добавлять описание в этот файл.

---

## Python Tests

### Unit Tests
- `tests/unit/` — модульные тесты Python кода

### Integration Tests
- `tests/integration/` — интеграционные тесты Python кода

---

## Rust Tests

### Unit Tests
- `crates/*/src/` — unit тесты внутри библиотек Rust

### Property-Based Tests

#### risk-ledger

**property_merkle**
- Тестирует дерево Меркла (Merkle Tree)
- 10,000 итераций на каждый тест
- Проверяет: генерацию proof, верификацию proof, консистентность root, высоту дерева

**property_validation**
- Тестирует double-entry валидацию
- 10,000 итераций на каждый тест
- Проверяет: балансировку транзакций, консистентность валидации, лимиты баланса

#### execution-core

**property_order_matching**
- Тестирует движок сопоставления ордеров (Order Matching Engine)
- 10,000 итераций на каждый тест
- Проверяет: исполнение market/limit ордеров, частичное заполнение, OCO ордера

**property_risk_calculation**
- Тестирует расчёты рисков (позиционирование, PnL, маржа, ликвидация)
- 10,000 итераций на каждый тест
- Проверяет: размер позиции, stop-loss, take-profit, плечо

---

## Как запускать тесты

### Python
```bash
.venv/bin/python -m pytest tests/ -v
```

### Rust
```bash
# Все тесты
cargo test --workspace

# Только property-based
cargo test -p cryptotechnolog-risk-ledger --test property
cargo test -p cryptotechnolog-execution-core --test property
```

### CI/CD
- `test-python` — Python тесты
- `test-rust` — Rust unit тесты
- `test-rust-property` — Rust property-based тесты

---

## Добавление новых тестов

При добавлении новых тестов:
1. Добавить тесты в соответствующую директорию
2. Обновить этот файл с описанием что тестируется
3. Убедиться что тесты проходят локально
4. Запушить и проверить CI
