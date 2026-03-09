# Priority Queues для HFT Event Bus

**Дата:** 2026-03-09  
**Статус:** Принято  

## Контекст
Фаза 3 расширила Event Bus с отдельными очередями для каждого приоритета.

- **Фаза:** 3 — Event Bus Enhancement
- **Компонент:** crates/eventbus/priority_queue.rs
- **Класс стратегии:** HFT (критическая производительность)

### Структура:
```rust
pub struct PriorityQueue {
    critical: VecDeque<Event>,  // CRITICAL_QUEUE_SIZE
    high: VecDeque<Event>,      // HIGH_QUEUE_SIZE
    normal: VecDeque<Event>,   // NORMAL_QUEUE_SIZE
    low: VecDeque<Event>,       // LOW_QUEUE_SIZE
}
```

### Ограничения размеров:
| Очередь | Размер | Поведение при переполнении |
|---------|--------|---------------------------|
| Critical | 100 | Block (синхронная обработка) |
| High | 1000 | Return error |
| Normal | 10000 | Return error |
| Low | 50000 | Drop oldest |

## Рассмотренные альтернативы
1. **Single queue с сортировкой** — O(n) вставка, медленно
2. **Heap-based priority queue** — лучше O(log n), но сложнее
3. **4 отдельных канала** — выбрано (O(1) вставка)

## Решение
Выбраны **отдельные VecDeque** для каждого приоритета:

### Преимущества:
- O(1) вставка и извлечение
- Предсказуемое поведение при переполнении
- Изоляция очередей (проблемы с low не влияют на critical)

## Последствия
### Плюсы:
- **Скорость** — O(1) операции
- **Изоляция** — critical не блокируется low
- **Простота** — понятная логика

### Минусы:
- **Memory overhead** — 4 очереди вместо 1
- **Load balancing** — одна high очередь может переполниться

## Связанные ADR
- ADR-0004: Система приоритетов событий
