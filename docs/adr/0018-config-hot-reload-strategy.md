# Стратегия Hot Reload для Config Manager

**Дата:** 2026-03-08  
**Статус:** Принято  

## Контекст
Фаза 4 проекта CRYPTOTEHNOLOG — реализация Config Manager.

- **Фаза:** 4 (Config Manager)
- **Класс стратегии:** SFT (Slow-Frequency Trading)
- **Компонент:** `src/cryptotechnolog/config/manager.py`

Необходимо обеспечить возможность обновления конфигурации без перезапуска торговой системы.

## Рассмотренные альтернативы
1. **Вариант А:** Polling — периодическая проверка файлов (каждые N секунд)
2. **Вариант Б:** Сигналы ОС (inotify на Linux, ReadDirectoryChangesW на Windows)
3. **Вариант В:** WebSocket или HTTP long-polling для удалённого обновления
4. **Вариант Г (выбрано):** Observer pattern + ConfigWatcher (библиотека watchdog)

## Решение
Реализован паттерн Observer с использованием библиотеки `watchdog`:

### ConfigWatcher
```python
class ConfigWatcher:
    """Мониторинг изменений файлов конфигурации."""
    
    def __init__(self, paths: list[Path]) -> None:
        self._observer = Observer()
        for path in paths:
            self._observer.schedule(self._handler, path, recursive=False)
    
    def on_change(self, callback: Callable[[], Any]) -> None:
        """Установить callback на изменение."""
        self._callback = callback
```

### Hot Reload в ConfigManager
```python
class ConfigManager:
    async def reload(self) -> SystemConfig:
        """Перезагрузить конфигурацию (hot reload)."""
        new_config = await self._load_config()
        
        # Проверка что конфигурация изменилась
        if new_config != self._current_config:
            self._current_config = new_config
            
            # Публикация события в Event Bus
            await self._event_bus.publish(
                event_type="CONFIG_UPDATED",
                payload={"version": new_config.version}
            )
        
        return self._current_config
```

### Событие CONFIG_UPDATED
При обновлении конфигурации публикуется событие:
- Подписаться могут: State Machine, Risk Engine, Strategy Manager
- Событие содержит: версию конфигурации, список изменённых полей

## Последствия
- **Плюсы:**
  - Мгновенное уведомление об изменениях
  - Не требует ручного вмешательства
  - Кроссплатформенная поддержка (Windows, Linux, macOS)
- **Минусы:**
  - Дополнительная зависимость (watchdog)
  - Необходимость обработки race conditions

## Связанные ADR
- ADR-0017: Config Manager Architecture SOLID (основа)
- ADR-0019: GPG Signature Verification (дополняет)
