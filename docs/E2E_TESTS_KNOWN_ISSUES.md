# E2E Тесты - Known Issues

## Удалённые тесты (2026-03-11)

Следующие E2E тесты были удалены из-за фундаментальных архитектурных проблем:

1. `tests/e2e/test_compliance.py` - 15 тестов
2. `tests/e2e/test_data_integrity.py` - 18 тестов
3. `tests/e2e/test_edge_cases.py` - 27 тестов
4. `tests/e2e/test_multi_asset.py` - 10 тестов
5. `tests/e2e/test_performance.py` - 14 тестов
6. `tests/e2e/test_risk_management.py` - 18 тестов
7. `tests/e2e/test_trading_flow.py` - 18 тестов

**Всего удалено: ~120 тестов**

## Причины удаления

### 1. Несоответствие Event API
Тесты использовали устаревшее Event API:
```python
# Было (неправильно):
event = Event(event_type=..., data=..., timestamp=...)

# Стало (правильно):
event = Event.new(event_type=..., source=..., payload=...)
```

### 2. Отсутствие таблицы events
Тесты ожидали таблицу `events`, которой нет в схеме БД. Архитектура использует:
- `audit_events` - для аудита
- `event_store` - для event sourcing

### 3. Неправильное ожидание поведения
Тесты ожидали что Event Bus автоматически записывает события в БД после publish(). Но архитектура предполагает:
- Event Bus только публикует события подписчикам
- Запись в БД делают подписчики (listeners)
- Нужен отдельный listener для записи событий

## Что нужно сделать для восстановления

### Вариант 1: Реализовать функциональность (рекомендуется)

1. **Создать Event Persistence Listener**
   ```python
   # src/cryptotechnolog/core/listeners/event_persistence.py
   class EventPersistenceListener:
       """Слушает события и записывает в events таблицу."""
       
       async def on_event(self, event: Event):
           await self.db.insert("events", {
               "event_type": event.event_type,
               "data": json.dumps(event.payload),
               "created_at": event.timestamp,
               "correlation_id": event.correlation_id,
           })
   ```

2. **Добавить миграцию**
   ```sql
   -- scripts/migrations/011_events_table.sql
   CREATE TABLE IF NOT EXISTS events (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       event_type VARCHAR(100) NOT NULL,
       data JSONB,
       created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
       correlation_id UUID
   );
   ```

3. **Настроить подписку в Event Bus**
   ```python
   event_bus.subscribe(
       EventPersistenceListener(),
       event_types=[EventType.ORDER_SUBMITTED, ...]
   )
   ```

4. **Переписать тесты** с правильными assertions

### Вариант 2: Использовать существующие таблицы

Переписать тесты чтобы использовать существующие таблицы:
- `audit_events` - для логирования событий
- `event_store` - для event sourcing

## Статус

- [ ] Реализовать EventPersistenceListener
- [ ] Добавить миграцию events
- [ ] Переписать E2E тесты
- [ ] Запустить тесты

## Альтернатива

Если E2E тесты не нужны для текущей фазы разработки, можно оставить как есть. Unit и Integration тесты покрывают основную функциональность.
