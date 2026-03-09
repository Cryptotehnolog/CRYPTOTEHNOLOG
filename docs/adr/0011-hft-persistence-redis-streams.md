# Persistence: Redis Streams для событий

**Дата:** 2026-03-09  
**Статус:** Принято  

## Контекст
Фаза 3 добавила persistence через Redis Streams для гарантии доставки.

- **Фаза:** 3 — Event Bus Enhancement
- **Компонент:** crates/eventbus/persistence.rs
- **Класс стратегии:** HFT (гарантия доставки)

### Зачем persistence:
1. **Перезапуски** — события не теряются при рестарте
2. **Replay** — возможность воспроизвести события
3. **Audit** — полная история для аудита

## Рассмотренные альтернативы
1. **PostgreSQL** — медленнее, надёжнее
2. **Kafka** — избыточно для этого проекта
3. **In-memory only** — данные теряются при рестарте

## Решение
Выбраны **Redis Streams**:

### Stream keys:
```
events:{event_type}  // по типу события
events:critical      // критические события
events:audit        // для аудита
```

### TTL:
| Тип | TTL | Причина |
|-----|-----|---------|
| Critical | 30 дней | Важно для аудита |
| High | 14 дней | Risk events |
| Normal | 7 дней | Стандартные |
| Low | 1 день | Метрики |

### Структура:
```rust
pub struct EventMetadata {
    pub delivery_attempt: u32,   // для retry
    pub expires_at: Option<u64>, // TTL
    pub persist: bool,           // флаг персистентности
    pub dedup_id: Option<String>, // exactly-once
}
```

## Последствия
### Плюсы:
- **Гарантия** — события сохраняются
- **Replay** — можно воспроизвести
- **Performance** — Redis быстрее PostgreSQL

### Минусы:
- **Сложность** — нужно управлять Streams
- **Memory** — Redis использует RAM
- **Consistency** — нужно обрабатывать ошибки

## Связанные ADR
- ADR-0005: Graceful Degradation
