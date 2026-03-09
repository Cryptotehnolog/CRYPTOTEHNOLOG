# Backpressure стратегия для HFT Event Bus

**Дата:** 2026-03-09  
**Статус:** Принято  

## Контекст
Фаза 3 определила стратегию backpressure для защиты от перегрузки.

- **Фаза:** 3 — Event Bus Enhancement
- **Компонент:** crates/eventbus/backpressure.rs
- **Класс стратегии:** HFT (защита от перегрузки)

### Стратегия:
| Приоритет | Поведение при переполнении |
|-----------|---------------------------|
| Critical | **BLOCK** — жди освобождения |
| High | **RETURN ERROR** — caller решает |
| Normal | **RETURN ERROR** — caller решает |
| Low | **DROP OLDEST** — удалить старое |

## Рассмотренные альтернативы
1. **Uniform backpressure** — всё блокируется или всё дропается
2. **Random drop** — случайное удаление
3. **头部压力 (head-of-line)** — приоритетная обработка

## Решение
Выбрана **приоритетная backpressure стратегия**:

### Логика:
```rust
match priority {
    Priority::Critical => {
        // Block until space available
        self.critical.push_back(event);
    }
    Priority::High | Priority::Normal => {
        // Return error, let caller decide
        return Err(QueueFullError);
    }
    Priority::Low => {
        // Drop oldest to make space
        self.low.pop_front();
        self.low.push_back(event);
    }
}
```

## Последствия
### Плюсы:
- **Гарантии** — Critical всегда обрабатывается
- **Гибкость** — High/Normal могут retry
- **Эффективность** — Low освобождает место

### Минусы:
- **Сложность** — разное поведение для разных приоритетов
- **Blocking risk** — Critical может заблокировать
- **Data loss** — Low события теряются

## Связанные ADR
- ADR-0005: Graceful Degradation
- ADR-0009: Priority Queues
