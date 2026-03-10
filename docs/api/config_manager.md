# API документация: Config Manager

## Обзор

Config Manager — центральный компонент системы управления конфигурацией в CRYPTOTEHNOLOG. 
Обеспечивает загрузку, валидацию, версионирование и hot reload конфигураций.

## Основные компоненты

### ConfigManager

```python
from cryptotechnolog.config.manager import ConfigManager

manager = ConfigManager(
    loader=provider,      # IConfigLoader
    parser=parser,       # IConfigParser
    validator=validator, # IConfigValidator
    signer=signer,       # IConfigSigner
    repository=None,     # IConfigRepository | None
    event_bus=None,      # EnhancedEventBus | None
)
```

#### Параметры конструктора

| Параметр | Тип | Описание |
|----------|-----|----------|
| `loader` | `IConfigLoader` | Загрузчик конфигурации (файл, Vault, env) |
| `parser` | `IConfigParser` | Парсер (YAML, JSON) |
| `validator` | `IConfigValidator` | Валидатор (Pydantic) |
| `signer` | `IConfigSigner` | Верификатор подписей (GPG) |
| `repository` | `IConfigRepository \| None` | Репозиторий для истории версий |
| `event_bus` | `EnhancedEventBus \| None` | Шина событий для алертов |

#### Основные методы

##### load()

```python
config = await manager.load(
    source="config.yaml",     # Источник конфигурации
    save_to_history=False,   # Сохранять в историю
    loaded_by="operator"      # Кто загрузил
)
```

##### reload()

```python
# Hot reload текущей конфигурации
config = await manager.reload(loaded_by="auto_reload")
```

##### load_from_history()

```python
# Загрузка конкретной версии из истории
config = await manager.load_from_history(version="1.0.0")
```

##### get_history()

```python
# Получить историю версий
history = await manager.get_history(limit=10)
```

##### get_latest_from_history()

```python
# Получить последнюю активную версию
latest = await manager.get_latest_from_history()
```

## Интерфейсы (Protocols)

### IConfigLoader

```python
class IConfigLoader(Protocol):
    async def load(self, source: str) -> bytes: ...
```

### IConfigParser

```python
class IConfigParser(Protocol):
    def parse(self, data: bytes) -> dict[str, Any]: ...
```

### IConfigValidator

```python
class IConfigValidator(Protocol):
    def validate(self, data: dict[str, Any]) -> SystemConfig: ...
```

### IConfigRepository

```python
class IConfigRepository(Protocol):
    async def save_version(
        self,
        version: str,
        content_hash: str,
        config_yaml: str,
        loaded_by: str,
    ) -> None: ...

    async def get_by_version(self, version: str) -> dict[str, Any] | None: ...
    async def get_history(self, limit: int) -> list[dict[str, Any]]: ...
    async def get_latest(self) -> dict[str, Any] | None: ...
```

### IConfigSigner

```python
class IConfigSigner(Protocol):
    async def verify(self, data: bytes, signature: bytes) -> bool: ...
```

## Провайдеры

### FileConfigProvider

```python
from cryptotechnolog.config.providers import FileConfigProvider

provider = FileConfigProvider(base_path=Path("/etc/config"))
```

### VaultConfigProvider

```python
from cryptotechnolog.config.providers import VaultConfigProvider

provider = VaultConfigProvider(
    vault_url="http://localhost:8200",
    mount_point="secret",
)
```

### EnvConfigProvider

```python
from cryptotechnolog.config.providers import EnvConfigProvider

provider = EnvConfigProvider(prefix="APP_")
```

## Парсеры

### YamlParser

```python
from cryptotechnolog.config.parsers import YamlParser

parser = YamlParser()
data = parser.parse(b"version: 1.0.0")
```

### JsonParser

```python
from cryptotechnolog.config.parsers import JsonParser

parser = JsonParser()
data = parser.parse(b'{"version": "1.0.0"}')
```

## Валидаторы

### PydanticValidator

```python
from cryptotechnolog.config.validators import PydanticValidator
from cryptotechnolog.config.models import SystemConfig

validator = PydanticValidator(schema=SystemConfig)
config = validator.validate(data)
```

## События

### CONFIG_UPDATED

Публикуется при изменении конфигурации:

```python
{
    "event_type": "CONFIG_UPDATED",
    "source": "CONFIG_MANAGER",
    "payload": {
        "old_version": "1.0.0",
        "new_version": "1.0.1",
        "changed_sections": ["risk", "exchanges"],
        "reload_required": {"risk": True},
    }
}
```

### CONFIG_ALERT

Публикуется при алертах:

```python
{
    "event_type": "CONFIG_ALERT",
    "source": "CONFIG_MANAGER",
    "payload": {
        "type": "validation_failed",
        "severity": "warning",
        "message": "Ошибка валидации...",
    }
}
```

## Метрики

ConfigManager предоставляет метрики:

- `config_load_total` — общее количество загрузок
- `config_load_success` — успешные загрузки
- `config_load_failed` — неудачные загрузки
- `config_validation_failed` — ошибки валидации
- `config_reload_total` — количество reload
- `config_reload_success` — успешные reload

## Примеры использования

### Базовый пример

```python
from pathlib import Path
from cryptotechnolog.config.manager import ConfigManager
from cryptotechnolog.config.providers import FileConfigProvider
from cryptotechnolog.config.parsers import YamlParser
from cryptotechnolog.config.validators import PydanticValidator, SystemConfig
from cryptotechnolog.config.signers import GPGSigner

# Создание компонентов
provider = FileConfigProvider(base_path=Path("/etc/cryptotehnolog"))
parser = YamlParser()
validator = PydanticValidator(schema=SystemConfig)
signer = GPGSigner(keyring_path=Path("/tmp/keyring"))

# Создание менеджера
manager = ConfigManager(
    loader=provider,
    parser=parser,
    validator=validator,
    signer=signer,
)

# Загрузка конфигурации
config = await manager.load(source="production.yaml")
print(f"Version: {config.version}")
```

### С историей версий

```python
from cryptotechnolog.config.repository import ConfigRepository

# С пулом PostgreSQL
repository = ConfigRepository(pool)

manager = ConfigManager(
    loader=provider,
    parser=parser,
    validator=validator,
    signer=signer,
    repository=repository,
)

# Загрузка с сохранением в историю
config = await manager.load(
    source="production.yaml",
    save_to_history=True,
    loaded_by="operator",
)

# Получить историю
history = await manager.get_history()
```

### С event bus

```python
from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus

event_bus = EnhancedEventBus()

manager = ConfigManager(
    loader=provider,
    parser=parser,
    validator=validator,
    signer=signer,
    event_bus=event_bus,
)

# Подписаться на события
async def on_config_updated(event):
    print(f"Config updated: {event.payload}")

await event_bus.subscribe("CONFIG_UPDATED", on_config_updated)

# Загрузка триггерит событие
config = await manager.load(source="production.yaml")
```

## Конфигурация (Pydantic Models)

### SystemConfig

```python
from cryptotechnolog.config.models import SystemConfig

# Базовая структура конфигурации
config = SystemConfig(
    version="1.0.0",
    environment="production",
    risk=RiskConfig(...),
    exchanges=[ExchangeConfig(...)],
    strategies=[StrategyConfig(...)],
    system=SystemSettings(...),
)
```

### RiskConfig

```python
from cryptotechnolog.config.models import RiskConfig

risk = RiskConfig(
    base_r_percent=Decimal("0.01"),      # 1% от R
    max_r_per_trade=Decimal("0.05"),      # макс 5% R за сделку
    max_drawdown_hard=Decimal("0.20"),   # хард лимит просадки 20%
    max_drawdown_soft=Decimal("0.10"),   # софт лимит 10%
    correlation_limit=Decimal("0.7"),    # лимит корреляции
)
```

## Тестирование

### Unit тесты

```python
import pytest
from cryptotechnolog.config.manager import ConfigManager

# Мок компоненты
loader = Mock(spec=IConfigLoader)
parser = Mock(spec=IConfigParser)
validator = Mock(spec=IConfigValidator)
signer = Mock(spec=IConfigSigner)

manager = ConfigManager(loader, parser, validator, signer)
```

### E2E тесты

```python
@pytest.mark.e2e
async def test_full_config_load(temp_config_file):
    """E2E тест полного цикла загрузки конфигурации."""
    manager = ConfigManager(...)
    config = await manager.load(source=str(temp_config_file))
    assert config.version == "1.0.0"
```

## Обработка ошибок

```python
try:
    config = await manager.load(source="config.yaml")
except ConfigManagerError as e:
    print(f"Ошибка: {e.operation} - {e.reason}")
except ValidationError as e:
    print(f"Ошибки валидации: {e.errors}")
```

## Best Practices

1. **Всегда используйте typed models** — Pydantic модели обеспечивают валидацию и автодокументацию
2. **Настраивайте repository** — для production критически важна история версий
3. **Подписывайтесь на events** — для мониторинга изменений конфигурации
4. **Используйте GPG подпись** — для production сред обязательна верификация
5. **Настраивайте alerts** — получайте уведомления о проблемах с конфигурацией
