# ADR-0013: Рефакторинг Python интерфейсов — interfaces.py, adapters.py, mocks

## Дата
2026-03-09

## Статус
Принято

## Контекст

При анализе кода Python компонентов (Фазы 0-3) было выявлено, что существующие компоненты имеют низкую тестируемость из-за отсутствия абстракций:

- Logger использует structlog напрямую без возможности подмены в тестах
- DatabaseManager не имеет абстрактного слоя для доступа к данным
- Нет возможности использовать in-memory реализации для быстрых изолированных тестов

## Рассмотренные альтернативы

### Вариант 1: Базовый Protocol внутри модулей (отклонён)
Быстрое решение — добавить Protocol внутрь каждого модуля (logging.py, database.py).
- Преимущества: Минимальные изменения
- Недостатки: Не соответствует SOLID (ISP), сложно масштабировать

### Вариант 2: Выделенные файлы interfaces.py и adapters.py (принят)
Создать отдельные модули для интерфейсов и их реализаций.
- Преимущества: Полное разделение ответственности, соответствует SOLID/DDD
- Недостатки: Больше файлов

## Решение

Создана многослойная архитектура:

### 1. Интерфейсы (`src/cryptotechnolog/core/interfaces.py`)
```python
class Logger(Protocol):
    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None: ...
    def info(self, msg: str, *args: Any, **kwargs: Any) -> None: ...
    # ...

class OrderRepository(Protocol):
    async def save(self, order: dict[str, Any]) -> None: ...
    async def find_by_id(self, order_id: str) -> dict[str, Any] | None: ...
    # ...
```

### 2. Адаптеры (`src/cryptotechnolog/core/adapters.py`)
```python
class StructlogAdapter:
    def __init__(self, name: str = None):
        self._logger = structlog.get_logger(name)
    # реализует Logger

class PostgresOrderRepository:
    def __init__(self, pool):
        self._pool = pool
    # реализует OrderRepository
```

### 3. Mocks для тестов (`tests/mocks/`)
```python
class MockLogger:
    def __init__(self):
        self.messages = []
    # методы assert_logged(), get_messages_by_level()

class InMemoryOrderRepository:
    def __init__(self):
        self._orders = {}
    # реализует OrderRepository
```

## Последствия

### Положительные
- **Тестируемость**: Компоненты теперь можно тестировать с моками без реальных зависимостей
- **SOLID**: Соблюдены принципы ISP (отдельные маленькие интерфейсы) и DIP (зависимости от абстракций)
- **DDD**: Domain repositories (Order, Position, RiskLimit) соответствуют Domain-Driven Design
- **Гибкость**: Легко подменить реализацию (например, PostgreSQL → SQLite)

### Отрицательные
- **Больше файлов**: 需要 создавать отдельные файлы для каждого слоя
- **Избыточность для HFT**: Для HFT-стратегий на Rust это может быть overkill

## Связанные ADR
- ADR-0001: Мультиязычная архитектура
- ADR-0002: Структура Rust workspace

## Пример использования

### Продакшен код
```python
from cryptotechnolog.core import Logger, StructlogAdapter
from cryptotechnolog.core import PostgresOrderRepository

logger: Logger = StructlogAdapter("order_service")
repo = PostgresOrderRepository(pool)
```

### Тест
```python
from tests.mocks import MockLogger, InMemoryOrderRepository

def test_order_creation():
    mock_logger = MockLogger()
    mock_repo = InMemoryOrderRepository()
    
    # Тестирование с изолированными моками
    order_service = OrderService(logger=mock_logger, repo=mock_repo)
    await order_service.create_order(...)
    
    mock_logger.assert_logged("INFO", "Order created")
```
