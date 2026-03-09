# Два Backend для Event Bus: LockFree и ChannelBased

**Дата:** 2026-03-09  
**Статус:** Принято  

## Контекст
Фаза 1 определила Event Bus как центральный компонент с двумя реализациями backend.

- **Фаза:** 1 — Ядро инфраструктуры
- **Компонент:** crates/eventbus
- **Класс стратегии:** HFT (критическая производительность)

### Почему потребовалось два backend:
1. **LockFree** — для высоконагруженных сценариев (>10k events/sec)
2. **ChannelBased** — для простоты и надёжности

## Рассмотренные альтернативы
1. **Только LockFree** — максимальная производительность, но сложность отладки
2. **Только ChannelBased** — проще, но недостаточно для HFT
3. **Другие решения** (tokio channels, crossbeam) — усложнение зависимостей

## Решение
Выбрана **dual-backend архитектура** с feature flag:

### LockFree Backend:
- Wait-free read operations
- Lock-free write operations
- Bounded capacity (предотвращает неконтролируемый рост памяти)
- ~50-100 ns/event (single-threaded), 200-500 ns/event (4 threads concurrent)

### ChannelBased Backend (по умолчанию):
- std::sync::mpsc channels
- Unbounded или bounded режимы
- Zero-copy message passing
- Backpressure support
- ~500-1000 ns/event

### Конфигурация:
```toml
# По умолчанию используется ChannelBased
[dependencies.cryptotechnolog-eventbus]
version = "0.1"

# Для HFT включить lock-free
[dependencies.cryptotechnolog-eventbus]
version = "0.1"
features = ["lock-free"]
```

## Последствия
### Плюсы:
- **Гибкость:** можно выбрать backend под требования
- **Постепенное внедрение:** LockFree отключён по умолчанию
- **Производительность:** для HFT доступен lock-free режим
- **Надёжность:** по умолчанию используется проверенный ChannelBased

### Минусы:
- **Сложность кода:** два backend требуют поддержки
- **Тестирование:** нужно тестировать оба варианта
- **Документация:** пользователи должны понимать когда какой выбрать

## Связанные ADR
- ADR-0001: Мультиязычная архитектура Python + Rust
