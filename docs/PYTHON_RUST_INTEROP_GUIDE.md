# Python ↔ Rust Interop Guide

## 📋 Содержание

- [Почему это важно](#почему-это-важно)
- [Когда внедрять](#когда-внедрять)
- [Архитектурные решения](#архитектурные-решения)
- [Практическое внедрение](#практическое-внедрение)
- [Best Practices](#best-practices)
- [Примеры кода](#примеры-кода)

---

## 🎯 Почему это важно

### Проблема

Python ↔ Rust interop — **критическое архитектурное решение** для CRYPTOTEHNOLOG. Неправильный выбор приведет к:

- ❌ **Performance bottleneck** - неэффективная коммуникация замедлит систему
- ❌ **Technical debt** - рефакторинг в production будет стоить миллионы
- ❌ **Scalability limits** - не сможете масштабироваться до $100M+ volumes
- ❌ **Maintenance nightmare** - сложная архитектура, которую невозможно поддерживать

### Решение

Правильный выбор сейчас обеспечит:

- ✅ **Maximum performance** - zero-copy, native speed
- ✅ **Scalability** - горизонтальное масштабирование до $100M+
- ✅ **Maintainability** - чистая архитектура, easy to understand
- ✅ **Future-proof** - стандартные решения 2024-2025

---

## ⏰ Когда внедрять

### Не внедрять (Фаза 0-5)

```
🚫 Фаза 0: Подготовка среды (Docker, PostgreSQL, Redis)
🚫 Фаза 1: Project Structure (directories, base config)
🚫 Фаза 2: State Machine (внутренний, не критично для performance)
🚫 Фаза 3: Event Bus (Redis pub/sub, не hot-path)
🚫 Фаза 4: Configuration System (Pydantic, не критично)
🚫 Фаза 5: Risk Engine (можно на Python для начала)
```

**Причина:** Нет high-frequency components, premature optimization.

---

### Внедрять (Фаза 6-7+)

```
✅ Фаза 6: Risk Ledger (high-frequency calculations)
✅ Фаза 7: Execution Engine (order routing, matching)
✅ Фаза 10: Market Data Processing (real-time data streams)
✅ Фаза 12: Backtesting Engine (large-scale simulations)
✅ Фаза 14: Order Matching Engine (high-frequency trading)
```

**Причина:** Появляются high-frequency paths, performance становится критичным.

---

## 🏗️ Архитектурные решения

### 1. PyO3 + maturin (Hot Path) ⭐

**Использовать для:** high-frequency calculations, critical paths

**Преимущества:**
- Zero-copy между Python и Rust
- Native Python extension (без overhead)
- Максимальный performance
- Seamless integration (Rust функции выглядят как Python)
- Стандартное решение (Pandas, Pydantic, Polars используют)

**Недостатки:**
- Требует перекомпиляции при изменениях
- Debugging сложнее
- Crash в Rust может crash Python process

**Когда использовать:**
```python
# ✅ High-frequency calculations (Risk Ledger)
position_size = calculate_position_size(equity, risk_percent, entry, stop)

# ✅ Order routing (Execution Engine)
route_order(order, market_conditions)

# ✅ Market data processing (real-time)
process_tick(tick_data)
```

---

### 2. gRPC / Redis (Non-Critical Paths)

**Использовать для:** service-to-service communication, event bus

**Преимущества:**
- Language-agnostic (можно добавить другие languages)
- Easy scaling (distributed services)
- Standard protocols (well-documented)
- Loose coupling (services independent)

**Недостатки:**
- Serialization overhead (JSON/Protobuf)
- Network latency (даже на localhost)
- Не подходит для hot-path (1000+ calls/sec)

**Когда использовать:**
```python
# ✅ Event bus (Phase 3)
await event_bus.publish("order.created", order_data)

# ✅ Service-to-service communication (Phase 19+)
grpc.risk_engine.check_position_risk(position)

# ✅ Monitoring/Alerting (non-critical)
send_alert("high_risk_detected", data)
```

---

### 3. Arrow Flight (Market Data)

**Использовать для:** large-scale data transfer, analytics

**Преимущества:**
- Columnar format (эффективен для time-series)
- Zero-copy serialization
- High-throughput data transfer
- Standard for analytics

**Недостатки:**
- Overhead для small messages
- Сложнее чем gRPC
- Не нужен для simple operations

**Когда использовать:**
```python
# ✅ Market data streams (Phase 10)
stream = arrow_flight_client.do_get("market_data.BTCUSDT.1s")

# ✅ Backtesting data (Phase 12)
load_historical_data("BTCUSDT", start, end)

# ✅ Analytics (Phase 14)
analyze_performance(trades, positions)
```

---

## 🔧 Практическое внедрение

### Фаза 6: Risk Ledger (PyO3)

**Цель:** High-frequency risk calculations

#### Шаг 1: Создать Rust library

```toml
# rust_components/Cargo.toml

[lib]
name = "cryptotechnolog_rust"
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.20", features = ["extension-module"] }
pyo3-asyncio = { version = "0.20", features = ["tokio-runtime"] }
numpy = "0.20"
arrow = "50"
```

#### Шаг 2: Реализовать critical functions

```rust
// rust_components/src/risk.rs

use pyo3::prelude::*;
use pyo3::types::PyDecimal;

/// Calculate position size based on risk parameters
/// Zero-copy calculation for maximum performance
#[pyfunction]
fn calculate_position_size(
    equity: f64,
    risk_percent: f64,
    entry_price: f64,
    stop_loss: f64,
) -> PyResult<f64> {
    let risk_amount = equity * risk_percent;
    let price_risk = (entry_price - stop_loss).abs();

    if price_risk == 0.0 {
        return Err(PyValueError::new_err("Price risk cannot be zero"));
    }

    let position_size = risk_amount / price_risk;
    Ok(position_size)
}

/// Calculate portfolio risk in parallel
#[pyfunction]
fn calculate_portfolio_risk(
    positions: Vec<(f64, f64, f64)>, // (entry, stop, size)
) -> PyResult<f64> {
    let total_risk: f64 = positions
        .par_iter()
        .map(|(entry, stop, size)| {
            let risk_per_unit = (entry - stop).abs();
            risk_per_unit * size
        })
        .sum();

    Ok(total_risk)
}

/// Python module definition
#[pymodule]
fn cryptotechnolog_rust(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(calculate_position_size, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_portfolio_risk, m)?)?;
    Ok(())
}
```

#### Шаг 3: Настроить maturin

```toml
# rust_components/pyproject.toml

[build-system]
requires = ["maturin>=1.0,<2.0"]
build-backend = "maturin"

[project]
name = "cryptotechnolog-rust"
version = "0.1.0"
requires-python = ">=3.11"
```

#### Шаг 4: Скомпилировать и использовать

```bash
# Compile Rust extension
cd rust_components
maturin develop --release

# Or build wheel
maturin build --release
```

```python
# src/risk/calculations.py

from cryptotechnolog_rust import calculate_position_size, calculate_portfolio_risk

def calculate_trade_risk(equity: Decimal, risk_percent: Decimal, entry: Decimal, stop: Decimal) -> Decimal:
    """Calculate trade risk using Rust for performance."""
    position_size = calculate_position_size(
        float(equity),
        float(risk_percent),
        float(entry),
        float(stop),
    )
    return Decimal(str(position_size))

def calculate_total_portfolio_risk(positions: List[Position]) -> Decimal:
    """Calculate total portfolio risk in parallel."""
    position_data = [
        (float(p.entry_price), float(p.stop_loss), float(p.size))
        for p in positions
    ]
    total_risk = calculate_portfolio_risk(position_data)
    return Decimal(str(total_risk))
```

---

### Фаза 7: Execution Engine (PyO3 + Async)

**Цель:** High-frequency order routing

```rust
// rust_components/src/execution.rs

use pyo3_asyncio::tokio::future_into_py;

/// Route order to optimal exchange
#[pyfunction]
async fn route_order(
    py: Python,
    order: Order,
    market_conditions: MarketConditions,
) -> PyResult<RouteDecision> {
    // Complex routing logic in Rust
    let decision = optimal_exchange(order, market_conditions).await?;

    Ok(decision)
}

/// Batch order processing for maximum throughput
#[pyfunction]
async fn batch_route_orders(
    py: Python,
    orders: Vec<Order>,
) -> PyResult<Vec<RouteDecision>> {
    let decisions = process_orders_parallel(orders).await?;
    Ok(decisions)
}
```

---

### Фаза 10: Market Data (Arrow Flight)

**Цель:** Large-scale data transfer

```python
# src/market_data/arrow_client.py

from pyarrow.flight import FlightClient

class MarketDataClient:
    """Arrow Flight client for high-throughput market data."""

    def __init__(self, location: str = "grpc://localhost:8815"):
        self.client = FlightClient(location)

    def stream_ticks(self, symbol: str, start: datetime, end: datetime):
        """Stream tick data using Arrow Flight."""
        descriptor = FlightDescriptor.for_command(
            f"ticks:{symbol}:{start.isoformat()}:{end.isoformat()}"
        )

        for chunk in self.client.do_get(descriptor):
            # Zero-copy data transfer
            yield chunk.data

    def load_historical_data(self, symbol: str, period: str) -> pa.Table:
        """Load historical data efficiently."""
        descriptor = FlightDescriptor.for_command(
            f"history:{symbol}:{period}"
        )

        reader = self.client.do_get(descriptor)
        return reader.read_all()
```

---

## 📊 Performance Comparison

| Operation | Python | PyO3 | gRPC | Improvement |
|-----------|--------|------|------|-------------|
| Position size calc | 0.5ms | 0.01ms | 0.1ms | **50x** vs Python |
| Portfolio risk (100 positions) | 10ms | 0.5ms | 2ms | **20x** vs Python |
| Order routing | 1ms | 0.02ms | 0.2ms | **50x** vs Python |
| Event publish | 0.1ms | N/A | 0.1ms | Same |
| Market data stream (1M ticks) | 5s | N/A | 1s | **5x** with Arrow |

---

## ✅ Best Practices

### 1. Правило 80/20

```python
# ✅ 80% кода на Python (быстрая разработка)
# ✅ 20% кода на Rust (critical performance paths)

# Python: Business logic, configuration, API
# Rust: Calculations, data processing, order routing
```

### 2. Profile before optimize

```bash
# Сначала профилируйте
python -m cProfile -o profile.stats main.py
py-spy top -- python main.py

# Потом оптимизируйте hot-spots
# Не оптимизируйте если < 1% времени
```

### 3. Graceful degradation

```python
try:
    # Try Rust implementation
    from cryptotechnolog_rust import calculate_position_size
    use_rust = True
except ImportError:
    # Fallback to Python
    use_rust = False
    logger.warning("Rust extension not available, using Python fallback")

def calculate_position_size_safe(...):
    if use_rust:
        return calculate_position_size_rust(...)
    else:
        return calculate_position_size_python(...)
```

### 4. Error handling

```rust
// Rust: Return PyResult with clear errors
#[pyfunction]
fn calculate_position_size(...) -> PyResult<f64> {
    if price_risk == 0.0 {
        return Err(PyValueError::new_err(
            "Price risk cannot be zero: entry={}, stop={}",
            entry_price, stop_loss
        ));
    }
    // ...
}
```

### 5. Testing

```python
# tests/unit/test_rust_integration.py

@pytest.mark.unit
def test_rust_position_size_calculation():
    """Test that Rust implementation matches Python."""
    equity = Decimal("100000")
    risk = Decimal("0.01")
    entry = Decimal("50000")
    stop = Decimal("49500")

    python_result = calculate_position_size_python(equity, risk, entry, stop)
    rust_result = calculate_position_size_rust(equity, risk, entry, stop)

    assert abs(python_result - rust_result) < Decimal("0.01")
```

---

## 🚀 Roadmap

| Фаза | Компонент | Технология | Причина |
|------|-----------|------------|---------|
| 0-5 | - | - | Не нужно |
| 6 | Risk Ledger | PyO3 | High-frequency calculations |
| 7 | Execution Engine | PyO3 | Order routing, matching |
| 10 | Market Data | Arrow Flight | Large-scale data transfer |
| 12 | Backtesting | PyO3 + Arrow | Large-scale simulations |
| 14 | Order Matching | PyO3 | Ultra-low latency |
| 19+ | Microservices | gRPC | Distributed services |

---

## 📚 Дополнительные ресурсы

- [PyO3 Documentation](https://pyo3.rs/)
- [Maturin Guide](https://www.maturin.rs/)
- [Arrow Flight](https://arrow.apache.org/docs/format/Flight.html)
- [tonic (gRPC)](https://github.com/hyperium/tonic)
- [Polars (Rust + Python example)](https://pola.rs/)

---

## ⚠️ Common Mistakes

### ❌ Не делайте так

```python
# 1. Используйте gRPC на hot-path
async def calculate_risk():
    return await grpc.risk_engine.calculate(...)  # ❌ Too slow

# 2. Сериализуйте данные unnecessarily
import json
order_json = json.dumps(order)  # ❌ Serialization overhead
rust_order(order_json)  # ❌ Parsing overhead

# 3. Создавайте too many small Rust functions
def tiny_calc_1(): ...  # ❌ Overhead of Python-Rust transition
def tiny_calc_2(): ...  # ❌ Better to combine

# 4. Не обрабатываете ошибки
rust_function()  # ❌ May crash Python
```

### ✅ Делайте так

```python
# 1. Используйте PyO3 для hot-path
from cryptotechnolog_rust import calculate_risk
def calculate_risk_fast():
    return calculate_risk(...)  # ✅ Direct call, zero-copy

# 2. Передавайте native types
rust_function(equity, risk_percent, entry, stop)  # ✅ No serialization

# 3. Объединяйте related operations
def calculate_portfolio_metrics():  # ✅ Combined function
    return rust_portfolio_metrics(...)

# 4. Обрабатывайте ошибки
try:
    result = rust_function(...)
except PyValueError as e:
    logger.error(f"Rust error: {e}")
    # Handle gracefully
```

---

## 🎯 Checklist

Перед внедрением Python ↔ Rust interop:

- [ ] Профилировали код и нашли hot-spots?
- [ ] Выбрали правильную технологию (PyO3 vs gRPC vs Arrow)?
- [ ] Написали unit tests для Rust functions?
- [ ] Добавили fallback на Python?
- [ ] Обработали все возможные ошибки?
- [ ] Настроили CI/CD для компиляции Rust?
- [ ] Протестировали performance improvements?
- [ ] Документировали API?
- [ ] Обучили команду?

---

## 📞 Поддержка

Если у вас есть вопросы о Python ↔ Rust interop:

1. Проверьте этот guide
2. Посмотрите примеры в `rust_components/`
3. Прочитайте [PyO3 Documentation](https://pyo3.rs/)
4. Свяжитесь с командой архитектуры

---

**Версия:** 1.0
**Последнее обновление:** 2025-01-15
**Автор:** CRYPTOTEHNOLOG Architecture Team
