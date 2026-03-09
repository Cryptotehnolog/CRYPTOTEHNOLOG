# Exponential Backoff с Jitter в Watchdog

**Дата:** 2026-03-09  
**Статус:** Принято  

## Контекст
При сбоях компонентов Watchdog использует retry с backoff. Без jitter несколько компонентов,重启 synchronously, могут создать Thundering Herd problem.
- Фаза 2 / Control Plane  
- Класс: SFT (retry логика не latency-critical)

## Рассмотренные альтернативы
1. Linear backoff — проще, но медленнее восстановление
2. Exponential backoff без jitter — может вызвать Thundering Herd
3. Exponential backoff с Full Jitter — выбрано (AWS best practice)

## Решение
Добавлен Full Jitter в `RecoveryStrategy`:
```python
def get_backoff_delay(self) -> float:
    delay = self.backoff_base * (self.backoff_multiplier**self._attempt)
    jitter = self._rng.uniform(0, self.jitter_factor)
    delay = delay * (1 + jitter)
    return min(delay, self.max_backoff)
```

Параметры:
- `jitter_factor=0.5` по умолчанию (50% случайного смещения)
- Использует `random.Random()` для воспроизводимости в тестах

## Последствия
- **Плюсы:** Избегание Thundering Herd, равномерное распределение retry, AWS best practice
- **Минусы:** Немного менее предсказуемое время восстановления

## Связанные ADR
- ADR-0008: Watchdog Health Monitoring
