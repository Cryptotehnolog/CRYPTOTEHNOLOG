# Архитектура Config Manager на основе SOLID принципов

**Дата:** 2026-03-08  
**Статус:** Принято  

## Контекст
Фаза 4 проекта CRYPTOTEHNOLOG — реализация Config Manager для централизованного управления конфигурацией.

- **Фаза:** 4 (Config Manager)
- **Класс стратегии:** SFT (Slow-Frequency Trading) — требуется полное соблюдение SOLID
- **Компонент:** `src/cryptotechnolog/config/`

Необходимо создать расширяемую систему управления конфигурацией с поддержкой:
- Множественных источников (файл, Vault, переменные окружения)
- Валидации через Pydantic
- GPG верификации подписей
- Hot reload без рестарта
- Истории версий в PostgreSQL

## Рассмотренные альтернативы
1. **Вариант А:** Один класс DatabaseManager с множеством методов (monolithic)
2. **Вариант Б:** Функциональный подход с отдельными функциями
3. **Вариант В (выбрано):** SOLID-ориентированная архитектура с протоколами и DI

## Решение
Реализована архитектура на основе SOLID принципов:

### Single Responsibility
Каждый класс имеет одну ответственность:
- `ConfigLoader` — загрузка конфигурации из источника
- `ConfigParser` — парсинг YAML/JSON в словарь
- `ConfigValidator` — валидация через Pydantic модели
- `ConfigSigner` — GPG проверка подписей
- `ConfigRepository` — хранение версий в PostgreSQL
- `ConfigWatcher` — мониторинг изменений файлов

### Open/Closed
Новые источники конфигурации добавляются через наследование `ConfigProviderProtocol` без изменения `ConfigManager`.

### Liskov Substitution
Все реализации `ConfigProviderProtocol` взаимозаменяемы:
```python
file_provider = FileConfigProvider(path="config.yaml")
vault_provider = VaultConfigProvider(paths={...})
env_provider = EnvConfigProvider()
```

### Interface Segregation
Узкие протоколы для разных задач:
- `IConfigLoader` — загрузка
- `IConfigParser` — парсинг
- `IConfigValidator` — валидация
- `IConfigSigner` — подписи

### Dependency Inversion
Зависимости от абстракций через конструктор:
```python
class ConfigManager:
    def __init__(
        self,
        loader: IConfigLoader,
        parser: IConfigParser,
        validator: IConfigValidator,
        signer: IConfigSigner,
        repository: IConfigRepository,
        event_bus: EnhancedEventBus,
    ) -> None:
```

### Структура файлов
```
src/cryptotechnolog/config/
├── protocols.py        # Протоколы (I)
├── manager.py          # ConfigManager (D)
├── providers.py        # Провайдеры
├── repository.py       # Репозиторий версий
├── watcher.py          # Мониторинг файлов
├── models.py           # Pydantic модели
├── parsers/            # Парсеры
├── validators/         # Валидаторы
└── signers/           # GPG подписи
```

## Последствия
- **Плюсы:**
  - Полная тестируемость через моки
  - Лёгкая замена реализаций
  - Расширяемость без изменения существующего кода
  - Соответствие требованиям SFT стратегий
- **Минусы:**
  - Большее количество файлов
  - Начальные затраты на архитектуру

## Связанные ADR
- ADR-0013: Python Interfaces Refactoring
- ADR-0018: Config Hot Reload Strategy (зависит)
- ADR-0019: GPG Signature Verification (зависит)
