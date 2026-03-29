# AI ПРОМТ: ФАЗА 4 - CONFIG MANAGER

## КОНТЕКСТ

Вы — Senior Python Engineer, специализирующийся на configuration management, security, и data validation.

**Фазы 0-3 завершены.** Доступны:
- Python окружение настроено
- Docker инфраструктура (Redis, PostgreSQL, Vault) работает
- Event Bus (Rust + Python bindings) работает
- Control Plane (State Machine) работает
- Database Layer, Logging доступны

**Текущая задача:** Создать централизованную систему управления конфигурацией с GPG-подписями, schema validation, hot reload, и Vault integration.

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: РУССКИЙ ЯЗЫК

**ВСЕ** комментарии, docstrings, логи и сообщения об ошибках должны быть **НА РУССКОМ ЯЗЫКЕ**.

### Python docstrings — ТОЛЬКО русский:

```python
class ConfigManager:
    """
    Менеджер конфигурации с поддержкой hot reload и GPG верификации.
    
    Особенности:
    - Валидация через Pydantic схемы
    - Проверка GPG подписей
    - История версий (Git-like)
    - Hot reload без рестарта
    - Секреты из Vault
    """
    
    async def load_config(self, path: Path) -> SystemConfig:
        """
        Загрузить конфигурацию из файла.
        
        Аргументы:
            path: Путь к YAML файлу
        
        Возвращает:
            Валидированная конфигурация
        
        Raises:
            SignatureError: Если подпись недействительна
            ValidationError: Если схема не валидна
        """
        pass
```

### Логи — ТОЛЬКО русский:

```python
logger.info("Конфигурация загружена", version=config.version)
logger.error("Подпись недействительна", file=config_path)
logger.warning("Обнаружено изменение конфигурации", path=watched_path)
logger.debug("Валидация схемы пройдена", config_size=len(yaml_content))
```

### Ошибки — ТОЛЬКО русский:

```python
raise SignatureError(f"Подпись не прошла проверку: {file_path}")
raise ValidationError(f"Недопустимое значение в схеме: {field}")
raise VaultError(f"Не удалось получить секрет из Vault: {secret_path}")
```

### Примеры замены:

| ❌ Неправильно | ✅ Правильно |
|----------------|--------------|
| "Config loaded" | "Конфигурация загружена" |
| "Signature invalid" | "Подпись недействительна" |
| "Hot reload triggered" | "Hot reload активирован" |
| "Vault connection failed" | "Ошибка подключения к Vault" |
| "Schema validation error" | "Ошибка валидации схемы" |

---

## 🔗 КОМПОНЕНТНЫЕ ИНТЕГРАЦИИ

### Роль компонента в системе:
Config Manager — единый источник настроек для всей системы CRYPTOTEHNOLOG. Все компоненты читают параметры через Config Manager. Hot reload позволяет менять лимиты риска, размеры позиций, параметры стратегий БЕЗ рестарта системы.

### Входящие зависимости (кто читает конфигурацию):

#### От всех компонентов (Фазы 1-22):

1. **Risk Engine (Фаза 5)** → читает risk limits
   - Параметры: `base_r_percent`, `max_r_per_trade`, `max_drawdown_hard`, `correlation_limit`
   - Частота: при старте + при CONFIG_UPDATED event
   - Действие: Обновить внутренние лимиты без рестарта
   - Hot reload: CRITICAL (изменение risk limits должно применяться немедленно)

2. **Execution Layer (Фаза 10)** → читает exchange settings
   - Параметры: `exchanges[].api_key_vault_path`, `exchanges[].rate_limits`, `exchanges[].enabled`
   - Частота: при старте + при CONFIG_UPDATED
   - Действие: Переподключиться к биржам с новыми параметрами
   - Hot reload: MEDIUM (может подождать до следующего цикла)

3. **Portfolio Governor (Фаза 9)** → читает position limits
   - Параметры: `max_position_size_usd`, `max_total_exposure_percent`, `max_positions_per_symbol`
   - Частота: каждую проверку позиции (~100 раз/сек)
   - Действие: Проверить лимиты перед открытием позиции
   - Hot reload: HIGH (новые лимиты применяются к следующим сделкам)

4. **State Machine (Фаза 2)** → читает system settings
   - Параметры: `boot_timeout_seconds`, `health_check_interval`, `degraded_mode_triggers`
   - Частота: при старте + при CONFIG_UPDATED
   - Действие: Обновить таймауты и пороги
   - Hot reload: LOW (редко меняется)

5. **Strategy Manager (Фаза 14)** → читает strategy parameters
   - Параметры: `strategies[].enabled`, `strategies[].params`, `strategies[].max_risk`
   - Частота: при старте + при CONFIG_UPDATED
   - Действие: Включить/выключить стратегии, обновить параметры
   - Hot reload: CRITICAL (быстрое отключение проблемных стратегий)

6. **Watchdog (Фаза 2)** → читает monitoring settings
   - Параметры: `circuit_breaker.failure_threshold`, `circuit_breaker.timeout_seconds`
   - Частота: при старте + при CONFIG_UPDATED
   - Действие: Обновить пороги circuit breaker
   - Hot reload: MEDIUM

7. **Operator Gate (Фаза 2)** → читает dual control settings
   - Параметры: `dual_control_required`, `approved_operators`, `request_timeout_minutes`
   - Частота: при проверке запросов
   - Действие: Применить новые правила безопасности
   - Hot reload: HIGH (security-critical)

8. **Vault Auth (Фаза 4)** → получает credentials
   - Параметры: Vault secrets по путям из конфига
   - Частота: при старте + rotation (каждые 24 часа)
   - Действие: Обновить API keys, tokens, passwords
   - Hot reload: CRITICAL (для credential rotation)

### Исходящие зависимости (что публикует Config Manager):

#### 1. → Event Bus (Фаза 1)
   - Событие: `CONFIG_UPDATED` (приоритет: HIGH)
   - Payload: `{"changed_sections": ["risk_limits"], "new_version": "v2.1.0", "diff": {...}}`
   - Частота: при обнаружении изменения файла (hot reload)
   - Подписчики: все компоненты (для hot reload)

#### 2. → Event Bus
   - Событие: `CONFIG_VALIDATION_FAILED` (приоритет: CRITICAL)
   - Payload: `{"errors": [...], "file": "config.yaml", "action": "keep_old_config"}`
   - Частота: при попытке загрузить невалидную конфигурацию
   - Подписчики: Observability, Telegram alerts

#### 3. → Event Bus
   - Событие: `CONFIG_SIGNATURE_INVALID` (приоритет: CRITICAL)
   - Payload: `{"file": "config.yaml", "expected_key": "...", "action": "reject"}`
   - Частота: при обнаружении неподписанной/подделанной конфигурации
   - Подписчики: Security monitoring, PagerDuty

#### 4. → Database (PostgreSQL)
   - Таблица: `config_versions`
   - Действие: Сохранить историю всех изменений конфигурации
   - Колонки: `version`, `content_hash`, `loaded_at`, `loaded_by`, `diff_from_previous`
   - Назначение: Audit trail, возможность rollback

#### 5. → Vault (HashiCorp)
   - Действие: Читать секреты по путям из конфигурации
   - Paths: `secret/data/cryptotehnolog/exchanges/bybit/api_key`, `secret/data/.../database/password`
   - Частота: при старте + rotation (24 часа)
   - Fallback: Если Vault недоступен → использовать кэшированные секреты (WARNING log)

#### 6. → File System
   - Действие: Watchdog мониторит изменения `config/*.yaml`
   - Trigger: inotify events (MODIFY, CREATE)
   - Действие при изменении: проверить подпись → валидировать → reload → публиковать CONFIG_UPDATED

### Контракты данных:

#### SystemConfig Schema (Pydantic):

```python
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional
from decimal import Decimal

class RiskConfig(BaseModel):
    """Конфигурация управления рисками."""
    
    base_r_percent: Decimal = Field(
        ge=0.001,
        le=0.05,
        description="Базовый риск на сделку (0.1% - 5%)"
    )
    
    max_r_per_trade: Decimal = Field(
        ge=0.005,
        le=0.10,
        description="Максимальный риск на одну сделку"
    )
    
    max_drawdown_hard: Decimal = Field(
        ge=0.05,
        le=0.50,
        description="Жесткий лимит просадки (5% - 50%)"
    )
    
    max_drawdown_soft: Decimal = Field(
        ge=0.03,
        le=0.30,
        description="Мягкий лимит просадки (предупреждение)"
    )
    
    correlation_limit: Decimal = Field(
        ge=0.5,
        le=1.0,
        description="Лимит корреляции между позициями"
    )
    
    @validator('max_drawdown_soft')
    def validate_soft_less_than_hard(cls, v, values):
        """Проверить что мягкий лимит меньше жесткого."""
        if 'max_drawdown_hard' in values and v >= values['max_drawdown_hard']:
            raise ValueError('Мягкий лимит просадки должен быть меньше жесткого')
        return v

class ExchangeConfig(BaseModel):
    """Конфигурация биржи."""
    
    name: str = Field(description="Имя биржи (bybit, okx, binance)")
    enabled: bool = Field(description="Включена ли биржа")
    api_key_vault_path: str = Field(description="Путь к API ключу в Vault")
    api_secret_vault_path: str = Field(description="Путь к secret в Vault")
    
    rate_limits: Dict[str, int] = Field(
        description="Rate limits: {'orders_per_second': 10, 'requests_per_minute': 1200}"
    )
    
    testnet: bool = Field(default=False, description="Использовать testnet")
    
    @validator('api_key_vault_path', 'api_secret_vault_path')
    def validate_vault_path(cls, v):
        """Проверить формат пути в Vault."""
        if not v.startswith('secret/data/'):
            raise ValueError(f"Vault путь должен начинаться с 'secret/data/', получено: {v}")
        return v

class StrategyConfig(BaseModel):
    """Конфигурация торговой стратегии."""
    
    name: str
    enabled: bool
    max_risk_r: Decimal = Field(ge=0.01, le=0.10)
    params: Dict[str, Any] = Field(description="Параметры специфичные для стратегии")
    
    exchanges: List[str] = Field(description="На каких биржах запускать")
    symbols: List[str] = Field(description="Торговые пары")

class SystemConfig(BaseModel):
    """Корневая конфигурация системы."""
    
    version: str = Field(description="Версия конфигурации (semver)")
    environment: str = Field(description="dev, staging, production")
    
    risk: RiskConfig
    exchanges: List[ExchangeConfig]
    strategies: List[StrategyConfig]
    
    system: Dict[str, Any] = Field(description="Системные настройки")
    
    class Config:
        # Запретить лишние поля
        extra = "forbid"
```

#### Config Version History (PostgreSQL):

```sql
CREATE TABLE config_versions (
    id SERIAL PRIMARY KEY,
    version VARCHAR(50) NOT NULL,
    content_hash VARCHAR(64) NOT NULL,  -- SHA256
    loaded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    loaded_by VARCHAR(100),  -- Оператор или 'auto_reload'
    diff_json JSONB,  -- Diff от предыдущей версии
    is_active BOOLEAN DEFAULT TRUE,
    config_yaml TEXT NOT NULL  -- Полный YAML для rollback
);

CREATE INDEX idx_config_versions_loaded_at ON config_versions(loaded_at DESC);
CREATE INDEX idx_config_versions_active ON config_versions(is_active) WHERE is_active = TRUE;
```

#### GPG Signature Format:

```
Файл: config/prod/config.yaml
Подпись: config/prod/config.yaml.sig (detached signature)

Проверка:
1. gpg --verify config.yaml.sig config.yaml
2. Проверить что ключ в trusted keyring
3. Проверить что срок действия ключа не истек
```

#### CONFIG_UPDATED Event:

```json
{
  "event_id": "evt_config_123",
  "event_type": "CONFIG_UPDATED",
  "priority": "High",
  "timestamp": 1704067200000000,
  "source": "config_manager",
  "payload": {
    "old_version": "v2.0.5",
    "new_version": "v2.1.0",
    "changed_sections": ["risk_limits", "strategies"],
    "diff": {
      "risk_limits.base_r_percent": {"old": 0.02, "new": 0.015},
      "strategies[0].enabled": {"old": true, "new": false}
    },
    "reload_required": {
      "risk_engine": true,
      "strategy_manager": true,
      "execution_layer": false
    }
  }
}
```

### Sequence Diagram (Config Hot Reload Flow):

```
[Operator] ──edit config.yaml──> [File System]
                                       |
                                       v
                                 [Watchdog]
                              (inotify MODIFY)
                                       |
                                       v
                              [Config Manager]
                                       |
                    ┌──────────────────┼──────────────────┐
                    v                  v                  v
            [Signature Check]  [Schema Validation]  [Load Secrets]
              GPG verify         Pydantic check      Vault API
                    |                  |                  |
                    v                  v                  v
                ✅ Valid           ✅ Valid           ✅ Loaded
                                       |
                                       v
                              [Update In-Memory]
                             self.config = new_config
                                       |
                                       v
                              [Persist to DB]
                            INSERT config_versions
                                       |
                                       v
                              [Event Bus: publish]
                              CONFIG_UPDATED event
                                       |
                    ┌──────────────────┼──────────────────┐
                    v                  v                  v
            [Risk Engine]      [Strategy Manager]    [Execution]
         reload risk limits   disable strategy[0]  (no action)
```

### Обработка ошибок интеграции:

#### 1. Invalid GPG signature:

```python
async def load_config(self, path: Path) -> SystemConfig:
    signature_path = path.with_suffix(path.suffix + '.sig')
    
    # Проверить подпись
    if not await self.verifier.verify(path, signature_path):
        logger.error(
            "❌ Подпись конфигурации недействительна",
            file=str(path),
            signature=str(signature_path),
        )
        
        # Публиковать CRITICAL событие
        await self.event_bus.publish(Event(
            event_type="CONFIG_SIGNATURE_INVALID",
            priority=Priority.Critical,
            source="config_manager",
            payload={"file": str(path), "action": "reject"},
        ))
        
        # НЕ загружать новую конфигурацию
        raise SignatureError(f"Подпись недействительна: {path}")
    
    # ... продолжить загрузку
```

**Действия:**
- Отклонить загрузку новой конфигурации
- Сохранить старую (последнюю валидную)
- CRITICAL alert в PagerDuty
- Логировать попытку (security audit)

#### 2. Schema validation error:

```python
try:
    config = SystemConfig.parse_obj(yaml_data)
except ValidationError as e:
    logger.error(
        "❌ Ошибка валидации схемы конфигурации",
        errors=e.errors(),
        file=str(path),
    )
    
    # Публиковать событие
    await self.event_bus.publish(Event(
        event_type="CONFIG_VALIDATION_FAILED",
        priority=Priority.Critical,
        source="config_manager",
        payload={
            "file": str(path),
            "errors": [{"field": err['loc'], "error": err['msg']} for err in e.errors()],
            "action": "keep_old_config",
        },
    ))
    
    # Сохранить старую конфигурацию
    logger.warning("Использую предыдущую валидную конфигурацию", version=self.config.version)
    
    raise
```

**Действия:**
- Отклонить невалидную конфигурацию
- Продолжить работу со старой
- WARNING alert (не CRITICAL, так как система работает)
- Детальное логирование ошибок валидации

#### 3. Vault unavailable:

```python
async def load_secrets_from_vault(self, config: SystemConfig) -> Dict[str, str]:
    secrets = {}
    
    try:
        for exchange in config.exchanges:
            # Попытка загрузить из Vault
            api_key = await self.vault_client.read_secret(exchange.api_key_vault_path)
            secrets[f"{exchange.name}.api_key"] = api_key
            
    except VaultError as e:
        logger.error(
            "❌ Ошибка подключения к Vault",
            error=str(e),
            fallback="using_cached_secrets",
        )
        
        # Fallback: использовать кэшированные секреты
        if self.cached_secrets:
            logger.warning(
                "⚠️  Используются КЭШИРОВАННЫЕ секреты",
                cached_age_hours=(datetime.now() - self.cache_timestamp).total_seconds() / 3600,
            )
            return self.cached_secrets
        else:
            # Нет кэша → критическая ошибка
            raise VaultError("Vault недоступен и нет кэшированных секретов")
    
    # Обновить кэш
    self.cached_secrets = secrets
    self.cache_timestamp = datetime.now()
    
    return secrets
```

**Fallback стратегия:**
- Использовать кэшированные секреты (до 24 часов)
- WARNING alert если используется кэш
- CRITICAL alert если нет кэша и Vault недоступен

#### 4. Hot reload race condition:

**Проблема:** Два компонента читают конфигурацию одновременно во время reload.

**Решение: Atomic config swap**

```python
class ConfigManager:
    def __init__(self):
        self._config: SystemConfig = None
        self._config_lock = asyncio.Lock()
        self._version = 0
    
    async def reload_config(self, path: Path):
        """Hot reload с атомарной заменой."""
        # Загрузить новую конфигурацию
        new_config = await self._load_and_validate(path)
        
        # Атомарная замена
        async with self._config_lock:
            old_version = self._version
            old_config = self._config
            
            self._config = new_config
            self._version += 1
            
            logger.info(
                "Конфигурация обновлена атомарно",
                old_version=old_config.version if old_config else None,
                new_version=new_config.version,
                internal_version=self._version,
            )
        
        # Публиковать событие ПОСЛЕ атомарной замены
        await self._publish_config_updated(old_config, new_config)
    
    def get_config(self) -> SystemConfig:
        """Получить текущую конфигурацию (thread-safe)."""
        # Чтение без lock (lock только на запись)
        return self._config
```

### Мониторинг интеграций:

#### Метрики Config Manager:

```python
# Счетчики
config_loads_total{status}  # status: success, signature_failed, validation_failed
config_reloads_total{trigger}  # trigger: file_change, manual, scheduled
config_vault_requests_total{secret_path, status}
config_validation_errors_total{field, error_type}

# Гистограммы
config_load_duration_seconds{phase, percentile}  # phase: signature, validation, vault, total
config_reload_duration_seconds{percentile}

# Gauges
config_version{environment}  # Текущая версия конфигурации
config_file_age_seconds{}  # Сколько секунд назад обновлялась
vault_secrets_cached{age_hours}  # Возраст кэшированных секретов
config_watchers_active{}  # Количество активных file watchers
```

#### Alerts:

**Critical (PagerDuty):**
- `config_loads_total{status="signature_failed"}` > 0
- `vault_secrets_cached{age_hours} > 24` (секреты слишком старые)
- `config_file_age_seconds > 604800` (конфигурация не обновлялась 7 дней в production)

**Warning (Telegram):**
- `config_loads_total{status="validation_failed"}` > 0
- `config_vault_requests_total{status="error"}` rate > 5/hour
- `config_reload_duration_seconds{p99} > 5` (reload слишком медленный)

---

## ⚠️ КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ ФАЗЫ 4

### Config Manager (с GPG + Vault):

**✅ Что реализовано:**
- Pydantic schema validation (strict typing)
- GPG signature verification (detached signatures)
- Version history (PostgreSQL audit trail)
- Hot reload (file watching + atomic swap)
- Vault integration (secrets management)
- Nested config access (dot notation)

**❌ Что НЕ реализовано (для future phases):**
- Distributed config sync (multi-instance)
- Config encryption at rest (только GPG signatures)
- Automatic rollback при failures
- Config diff UI/dashboard
- Remote config updates (только file-based)

**⚠️ ВАЖНО:**
```markdown
Config Manager в Фазе 4 работает с локальными файлами.
Для distributed deployment требуется:
- Фаза 18: etcd/Consul для distributed config
- Shared file system (NFS/GlusterFS) ИЛИ config API

GPG signatures защищают от подделок, но НЕ шифруют:
- YAML файлы читаемы в plain text
- Секреты ДОЛЖНЫ храниться в Vault (не в YAML)

Hot reload требует осторожности:
- Изменение critical параметров может нарушить работу
- Рекомендуется testing в staging перед production
```

### Production Readiness Matrix:

| Компонент | После Фазы 4 | Production Ready |
|-----------|--------------|------------------|
| Schema Validation | ✅ Ready | ✅ Ready |
| GPG Signatures | ✅ Ready | ✅ Ready с key rotation |
| Vault Integration | ✅ Ready | ✅ Ready с HA Vault |
| Hot Reload | ✅ Ready | ⚠️ Требует testing protocol |
| Version History | ✅ Ready | ✅ Ready |

---

## ЦЕЛЬ ФАЗЫ

Создать production-ready Config Manager с:

1. **Pydantic Schema Validation** — строгая типизация всех параметров
2. **GPG Signature Verification** — защита от подделок
3. **Version History** — Git-like версионирование
4. **Hot Reload** — обновление без рестарта
5. **Vault Integration** — секреты из HashiCorp Vault
6. **Nested Access** — удобный доступ к вложенным значениям

---

## ФАЙЛОВАЯ СТРУКТУРА

Создайте следующие файлы с ПОЛНЫМ рабочим кодом:

```
CRYPTOTEHNOLOG/
├── src/
│   └── core/
│       ├── config_schema.py (NEW)
│       ├── signature_verifier.py (NEW)
│       ├── config_manager.py (NEW)
│       └── config_watcher.py (NEW)
│
├── config/
│   └── dev/
│       ├── config.yaml (NEW - example)
│       └── config.yaml.sig (NEW - signature)
│
├── tests/
│   ├── unit/
│   │   ├── test_config_schema.py (NEW)
│   │   ├── test_signature_verifier.py (NEW)
│   │   └── test_config_manager.py (NEW)
│   └── integration/
│       └── test_config_full_flow.py (NEW)
│
└── scripts/
    └── sign_config.py (NEW - helper script)
```

---

## ЗАВИСИМОСТИ

### Существующие (из Фаз 1-3):
```python
from src.core.logger import get_logger
from src.core.database import PostgreSQLManager
```

### Новые (добавьте в requirements.txt):
```txt
# Existing: structlog, asyncpg, redis, pydantic, fastapi, etc.

# NEW for Phase 4:
pyyaml==6.0.1
python-gnupg==0.5.1
hvac==2.0.0  # HashiCorp Vault client
watchdog==3.0.0  # File watching
```

---

## ТРЕБОВАНИЯ

### 1. Configuration Schema (src/core/config_schema.py)

**Создайте полную Pydantic схему:**

```python
from pydantic import BaseModel, Field, validator, root_validator
from typing import List, Dict, Optional
from enum import Enum
from decimal import Decimal


class ExchangeType(str, Enum):
    BYBIT = "bybit"
    OKX = "okx"
    BINANCE = "binance"


class ExchangeConfig(BaseModel):
    name: ExchangeType
    enabled: bool = True
    weight: float = Field(ge=0.0, le=1.0)
    
    # Vault paths (not actual secrets)
    api_key_vault_path: str
    api_secret_vault_path: str
    
    max_orders_per_second: int = Field(ge=1, le=100)
    max_positions: int = Field(ge=1, le=100)
    max_latency_ms: int = Field(ge=10, le=5000)
    min_uptime_percent: float = Field(ge=0.9, le=1.0)


class RiskConfig(BaseModel):
    # R-Unit system
    base_r_percent: Decimal = Field(ge=0.001, le=0.05)
    max_r_per_trade: Decimal = Field(ge=0.005, le=0.10)
    max_portfolio_r: Decimal = Field(ge=0.05, le=0.50)
    
    # Drawdown limits
    soft_drawdown_percent: Decimal = Field(ge=0.05, le=0.30)
    hard_drawdown_percent: Decimal = Field(ge=0.10, le=0.50)
    
    # Position limits
    max_positions: int = Field(ge=1, le=50)
    max_correlated_positions: int = Field(ge=1, le=10)
    
    # Volatility regimes
    volatility_atr_low: float = Field(ge=0.1, le=0.8)
    volatility_atr_normal: float = Field(ge=0.8, le=1.2)
    volatility_atr_high: float = Field(ge=1.2, le=2.0)
    
    @root_validator
    def validate_drawdown_order(cls, values):
        # MUST: Ensure soft_drawdown < hard_drawdown
        pass
    
    @root_validator
    def validate_r_limits(cls, values):
        # MUST: Ensure max_r_per_trade <= max_portfolio_r
        pass


class CorrelationGroup(BaseModel):
    name: str
    symbols: List[str] = Field(min_items=1)
    max_exposure_percent: Decimal = Field(ge=0.1, le=1.0)


class SessionRegimeConfig(BaseModel):
    name: str
    start_hour_utc: int = Field(ge=0, le=23)
    end_hour_utc: int = Field(ge=0, le=23)
    r_multiplier: float = Field(ge=0.1, le=2.0)


class StrategyConfig(BaseModel):
    enabled: bool = True
    version: str
    parameters: Dict[str, float]
    min_confidence: float = Field(ge=0.0, le=1.0)
    max_signals_per_hour: int = Field(ge=1, le=100)


class ObservabilityConfig(BaseModel):
    metrics_enabled: bool = True
    metrics_flush_interval_seconds: int = Field(ge=10, le=300)
    
    # SLO targets
    slo_execution_latency_p99_ms: int = Field(ge=1, le=100)
    slo_uptime_percent: float = Field(ge=0.99, le=1.0)
    
    # Telegram (secrets in Vault)
    telegram_enabled: bool = True
    telegram_bot_token_vault_path: str
    telegram_chat_id_vault_path: str


class SystemConfig(BaseModel):
    """Root configuration schema."""
    
    # Metadata
    version: str = Field(regex=r'^\d+\.\d+\.\d+$')
    environment: str = Field(regex=r'^(dev|staging|production)$')
    
    # Components
    exchanges: List[ExchangeConfig] = Field(min_items=1)
    risk: RiskConfig
    correlation_groups: List[CorrelationGroup]
    session_regimes: List[SessionRegimeConfig]
    strategies: Dict[str, StrategyConfig]
    observability: ObservabilityConfig
    
    # System
    max_startup_time_seconds: int = Field(ge=10, le=300)
    graceful_shutdown_timeout_seconds: int = Field(ge=5, le=60)
    
    class Config:
        extra = "forbid"  # Reject unknown fields
    
    @validator('exchanges')
    def validate_exchange_weights(cls, exchanges):
        # MUST: Ensure enabled exchange weights sum to ~1.0 (0.99-1.01)
        pass
```

**Требования:**
- Все поля типизированы (int, float, Decimal, str, Enum)
- Validators проверяют бизнес-логику
- extra="forbid" блокирует неизвестные поля
- Decimal для финансовых значений (не float)

---

### 2. Signature Verifier (src/core/signature_verifier.py)

**Создайте GPG signature verification:**

```python
import gnupg
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class VerificationResult:
    valid: bool
    fingerprint: Optional[str]
    username: Optional[str]
    key_id: Optional[str]
    timestamp: Optional[int]
    error: Optional[str] = None


class SignatureVerifier:
    def __init__(self, gnupg_home: Optional[Path] = None):
        # MUST:
        # 1. Create GPG instance with gnupghome
        # 2. Initialize trusted_fingerprints set
        self.gpg = gnupg.GPG(gnupghome=str(gnupg_home) if gnupg_home else None)
        self.trusted_fingerprints: set[str] = set()
    
    def import_public_key(self, key_path: Path) -> bool:
        # MUST:
        # 1. Read key file
        # 2. Call gpg.import_keys(key_data)
        # 3. Add fingerprints to trusted_fingerprints
        # 4. Return True if successful
        pass
    
    def verify_file(
        self,
        file_path: Path,
        signature_path: Path,
    ) -> VerificationResult:
        # MUST:
        # 1. Read file content (binary)
        # 2. Read signature (binary)
        # 3. Call gpg.verify_data(signature_data, file_data)
        # 4. Check if verified.valid
        # 5. Check if verified.fingerprint in trusted_fingerprints
        # 6. Return VerificationResult
        pass
    
    def sign_file(
        self,
        file_path: Path,
        output_path: Path,
        key_id: str,
        passphrase: Optional[str] = None,
    ) -> bool:
        # MUST:
        # 1. Read file data
        # 2. Call gpg.sign(data, keyid, passphrase, detach=True)
        # 3. Write signature to output_path
        # 4. Return True if successful
        pass
```

**Требования:**
- Detached signatures (.sig files)
- Trusted fingerprint enforcement
- Detailed error messages
- Tamper detection

---

### 3. Config Manager (src/core/config_manager.py)

**Создайте ConfigManager:**

```python
from pathlib import Path
from typing import Optional, Any, Dict, List
from datetime import datetime
from dataclasses import dataclass
import yaml
import hvac


@dataclass
class ConfigVersion:
    version_id: int
    config: SystemConfig
    loaded_at: datetime
    signature_verified: bool
    signature_fingerprint: Optional[str]
    file_path: str
    file_hash: str  # SHA-256


class ConfigManager:
    def __init__(
        self,
        db: PostgreSQLManager,
        vault_client: hvac.Client,
        signature_verifier: SignatureVerifier,
    ):
        self.db = db
        self.vault = vault_client
        self.signature_verifier = signature_verifier
        
        self.current_config: Optional[SystemConfig] = None
        self.current_version_id: int = 0
        self.version_history: List[ConfigVersion] = []
        self.max_history_size: int = 10
        self.secrets_cache: Dict[str, str] = {}
    
    async def load_config(
        self,
        config_path: Path,
        signature_path: Optional[Path] = None,
        require_signature: bool = True,
    ) -> bool:
        # MUST implement:
        # 
        # 1. Verify signature (if signature_path exists)
        #    - Call signature_verifier.verify_file()
        #    - If invalid and require_signature: raise RuntimeError
        #    - If invalid: log CRITICAL, trigger KillSwitch
        # 
        # 2. Load YAML
        #    - yaml.safe_load(file)
        #    - Handle parse errors
        # 
        # 3. Validate schema
        #    - SystemConfig(**config_data)
        #    - Catch ValidationError
        # 
        # 4. Load secrets from Vault
        #    - Call _load_secrets(config)
        # 
        # 5. Calculate file hash
        #    - SHA-256 of file content
        # 
        # 6. Create ConfigVersion
        #    - Increment version_id
        #    - Create ConfigVersion dataclass
        # 
        # 7. Update current_config
        # 
        # 8. Add to version_history
        #    - Keep only last max_history_size versions
        # 
        # 9. Persist to database
        #    - Call _persist_version()
        # 
        # 10. Return True
        pass
    
    async def _load_secrets(self, config: SystemConfig):
        # MUST:
        # 1. Collect all vault paths from config
        #    - exchanges[].api_key_vault_path
        #    - exchanges[].api_secret_vault_path
        #    - observability.telegram_*_vault_path
        # 
        # 2. For each path:
        #    - vault.secrets.kv.v2.read_secret_version(path=path)
        #    - Cache secrets in secrets_cache
        # 
        # 3. Handle errors (missing secrets)
        pass
    
    def get_secret(self, vault_path: str, key: str = "value") -> Optional[str]:
        # Return from secrets_cache
        pass
    
    def get(self, key_path: str, default: Any = None) -> Any:
        # MUST implement nested access:
        # 
        # Examples:
        # - get("risk.max_r_per_trade") → Decimal('0.02')
        # - get("exchanges[0].name") → "bybit"
        # - get("strategies.donchian_breakout.enabled") → True
        # 
        # Implementation:
        # 1. Split key_path by '.'
        # 2. For each part:
        #    - Handle list indexing: exchanges[0]
        #    - Handle dict access: strategies[key]
        #    - Handle attribute access: config.risk
        # 3. Return value or default
        pass
    
    async def hot_reload(self, config_path: Path) -> bool:
        # MUST:
        # 1. Call load_config(config_path)
        # 2. If successful: notify components (via Event Bus)
        # 3. Return success status
        pass
    
    async def rollback(self, version_id: Optional[int] = None) -> bool:
        # MUST:
        # 1. If version_id is None: rollback to previous version
        # 2. Else: rollback to specific version_id
        # 3. Update current_config
        # 4. Return success
        pass
    
    async def _persist_version(self, version: ConfigVersion):
        # MUST:
        # 1. Serialize config to dict (config.dict())
        # 2. INSERT into config_versions table
        pass
    
    async def init_schema(self):
        # MUST create table:
        """
        CREATE TABLE IF NOT EXISTS config_versions (
            version_id INTEGER PRIMARY KEY,
            config_data JSONB NOT NULL,
            loaded_at TIMESTAMPTZ NOT NULL,
            signature_verified BOOLEAN NOT NULL,
            signature_fingerprint VARCHAR(100),
            file_path TEXT NOT NULL,
            file_hash VARCHAR(64) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        CREATE INDEX idx_config_versions_loaded_at ON config_versions(loaded_at DESC);
        """
        pass
```

**Требования:**
- Signature verification перед загрузкой
- Schema validation обязательна
- Vault secrets загружаются при load_config
- Version history limited to 10
- Database persistence

---

### 4. Config Watcher (src/core/config_watcher.py)

**Создайте file watcher для hot reload:**

```python
import asyncio
from pathlib import Path
from typing import Callable, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent


class ConfigFileHandler(FileSystemEventHandler):
    def __init__(self, config_path: Path, callback: Callable):
        self.config_path = config_path
        self.callback = callback
    
    def on_modified(self, event: FileModifiedEvent):
        # MUST:
        # 1. Check if event.src_path == config_path
        # 2. If yes: asyncio.create_task(callback())
        pass


class ConfigWatcher:
    def __init__(self, config_manager: ConfigManager, config_path: Path):
        self.config_manager = config_manager
        self.config_path = config_path
        self.observer: Optional[Observer] = None
        self.is_watching = False
    
    async def start_watching(self):
        # MUST:
        # 1. Create ConfigFileHandler with callback=_on_config_changed
        # 2. Create Observer
        # 3. observer.schedule(handler, path=config_path.parent)
        # 4. observer.start()
        pass
    
    async def stop_watching(self):
        # MUST:
        # 1. observer.stop()
        # 2. observer.join()
        pass
    
    async def _on_config_changed(self):
        # MUST:
        # 1. Debounce (sleep 1 second)
        # 2. Call config_manager.hot_reload(config_path)
        # 3. Handle errors
        pass
```

---

### 5. Example Config (config/dev/config.yaml)

**Создайте пример конфигурации:**

```yaml
version: "1.0.0"
environment: "dev"

exchanges:
  - name: "bybit"
    enabled: true
    weight: 0.5
    api_key_vault_path: "exchanges/bybit"
    api_secret_vault_path: "exchanges/bybit"
    max_orders_per_second: 10
    max_positions: 20
    max_latency_ms: 500
    min_uptime_percent: 0.95
  
  - name: "okx"
    enabled: true
    weight: 0.5
    api_key_vault_path: "exchanges/okx"
    api_secret_vault_path: "exchanges/okx"
    max_orders_per_second: 10
    max_positions: 20
    max_latency_ms: 500
    min_uptime_percent: 0.95

risk:
  base_r_percent: 0.01
  max_r_per_trade: 0.02
  max_portfolio_r: 0.20
  soft_drawdown_percent: 0.10
  hard_drawdown_percent: 0.20
  max_positions: 10
  max_correlated_positions: 3
  volatility_atr_low: 0.8
  volatility_atr_normal: 1.2
  volatility_atr_high: 1.8

correlation_groups:
  - name: "majors"
    symbols: ["BTC/USDT", "ETH/USDT"]
    max_exposure_percent: 0.40

session_regimes:
  - name: "london_ny"
    start_hour_utc: 8
    end_hour_utc: 20
    r_multiplier: 1.0

strategies:
  donchian_breakout:
    enabled: true
    version: "1.0.0"
    parameters:
      lookback_period: 20
      atr_multiplier: 2.0
    min_confidence: 0.6
    max_signals_per_hour: 5

observability:
  metrics_enabled: true
  metrics_flush_interval_seconds: 60
  slo_execution_latency_p99_ms: 5
  slo_uptime_percent: 0.999
  telegram_enabled: true
  telegram_bot_token_vault_path: "telegram/bot_token"
  telegram_chat_id_vault_path: "telegram/chat_id"

max_startup_time_seconds: 60
graceful_shutdown_timeout_seconds: 30
```

---

### 6. Helper Script (scripts/sign_config.py)

**Создайте скрипт для подписания конфигов:**

```python
#!/usr/bin/env python3
"""
Sign configuration file with GPG.

Usage:
    python scripts/sign_config.py config/dev/config.yaml --key-id ABC123
"""

import argparse
from pathlib import Path
from src.core.signature_verifier import SignatureVerifier


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('config_path', type=Path)
    parser.add_argument('--key-id', required=True)
    parser.add_argument('--passphrase', default=None)
    args = parser.parse_args()
    
    verifier = SignatureVerifier()
    
    signature_path = Path(str(args.config_path) + ".sig")
    
    success = verifier.sign_file(
        args.config_path,
        signature_path,
        args.key_id,
        args.passphrase,
    )
    
    if success:
        print(f"✅ Signed: {signature_path}")
    else:
        print("❌ Signing failed")
        exit(1)


if __name__ == "__main__":
    main()
```

---

## ТЕСТЫ

### Unit Tests

**tests/unit/test_config_schema.py:**
```python
def test_valid_risk_config():
    risk = RiskConfig(
        base_r_percent=Decimal("0.01"),
        max_r_per_trade=Decimal("0.02"),
        max_portfolio_r=Decimal("0.20"),
        soft_drawdown_percent=Decimal("0.10"),
        hard_drawdown_percent=Decimal("0.20"),
        # ...
    )
    assert risk.base_r_percent == Decimal("0.01")


def test_invalid_drawdown_order():
    with pytest.raises(ValidationError):
        RiskConfig(
            soft_drawdown_percent=Decimal("0.25"),  # >= hard
            hard_drawdown_percent=Decimal("0.20"),
            # ...
        )


def test_exchange_weights_must_sum_to_one():
    with pytest.raises(ValidationError):
        SystemConfig(
            exchanges=[
                ExchangeConfig(name="bybit", weight=0.5, ...),
                ExchangeConfig(name="okx", weight=0.3, ...),  # Total 0.8
            ],
            # ...
        )
```

**tests/unit/test_signature_verifier.py:**
```python
def test_verify_signed_file(verifier, tmp_path):
    # Generate key, sign file, verify
    pass


def test_detect_tampered_file(verifier, tmp_path):
    # Sign file, tamper, verify should fail
    pass
```

---

## 🚀 ПРОИЗВОДИТЕЛЬНОСТЬ И МАСШТАБИРУЕМОСТЬ

### Критические требования к производительности:

```
Операция                      Latency Target    Частота
─────────────────────────────────────────────────────────────────
get_config()                  <10μs             Постоянно (каждая сделка)
validate_schema()             <50ms             При hot reload
verify_gpg_signature()        <200ms            При hot reload
load_secrets_from_vault()     <500ms            При старте + rotation
hot_reload (full)             <1s               При изменении файла
nested_access (config.get())  <5μs              Постоянно
─────────────────────────────────────────────────────────────────
```

### Критические узкие места:

#### 1. Config access на hot path (100+ раз/сек)

**Проблема:** Risk Engine проверяет `config.risk.max_r_per_trade` при каждой сделке (100+ раз/сек).

**Решение: In-memory cache с lock-free reads**

```python
class ConfigManager:
    def __init__(self):
        self._config: SystemConfig = None
        self._config_lock = asyncio.Lock()  # Lock только для записи
        
        # Cache для частых запросов
        self._cache: Dict[str, Any] = {}
        self._cache_version = 0
    
    def get_config(self) -> SystemConfig:
        """
        Получить конфигурацию (lock-free read).
        
        КРИТИЧНО: метод НЕ блокируется даже во время hot reload.
        """
        # Чтение без lock (Python GIL гарантирует атомарность)
        return self._config
    
    def get(self, path: str, default: Any = None) -> Any:
        """
        Получить значение по пути (dot notation) с кэшированием.
        
        Примеры:
            config.get("risk.base_r_percent")
            config.get("exchanges.0.name")
            config.get("strategies.momentum.params.period", default=14)
        
        Производительность: <5μs (кэшированные значения)
        """
        # Проверить кэш
        cache_key = f"{self._cache_version}:{path}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Получить из конфигурации
        config = self._config
        if config is None:
            return default
        
        # Навигация по path
        value = config
        for part in path.split('.'):
            if part.isdigit():
                # Индекс списка
                value = value[int(part)]
            else:
                # Атрибут объекта
                value = getattr(value, part, default)
                if value is default:
                    return default
        
        # Кэшировать результат
        self._cache[cache_key] = value
        return value
    
    async def reload_config(self, path: Path):
        """Hot reload с инвалидацией кэша."""
        new_config = await self._load_and_validate(path)
        
        async with self._config_lock:
            # Атомарная замена
            self._config = new_config
            
            # Инвалидация кэша
            self._cache_version += 1
            self._cache.clear()
            
            logger.info("Конфигурация и кэш обновлены", version=new_config.version)
```

**Результат:**
- `get_config()`: 0 locks, instant read
- `get("risk.base_r_percent")`: ~5μs (кэшированное значение)
- Hot reload НЕ блокирует читателей

#### 2. GPG signature verification bottleneck

**Проблема:** GPG verification ~200ms → блокирует hot reload.

**Решение: Async verification + result caching**

```python
class SignatureVerifier:
    def __init__(self):
        self.gpg = gnupg.GPG()
        self._verified_cache: Dict[str, Tuple[bool, datetime]] = {}
        self._cache_ttl = timedelta(minutes=5)
    
    async def verify_file_async(self, file_path: Path, sig_path: Path) -> bool:
        """
        Асинхронная проверка подписи (не блокирует event loop).
        """
        # Проверить кэш
        cache_key = f"{file_path}:{sig_path}"
        if cache_key in self._verified_cache:
            result, timestamp = self._verified_cache[cache_key]
            if datetime.now() - timestamp < self._cache_ttl:
                logger.debug("GPG signature проверена из кэша", file=file_path)
                return result
        
        # Выполнить проверку в thread pool (CPU-bound)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,  # Default thread pool
            self._verify_sync,
            file_path,
            sig_path,
        )
        
        # Кэшировать результат
        self._verified_cache[cache_key] = (result, datetime.now())
        
        return result
    
    def _verify_sync(self, file_path: Path, sig_path: Path) -> bool:
        """Синхронная проверка (CPU-bound, выполняется в отдельном потоке)."""
        with open(sig_path, 'rb') as sig_file:
            verified = self.gpg.verify_file(sig_file, str(file_path))
        
        return verified.valid
```

**Результат:**
- Verification не блокирует async event loop
- Кэшированные проверки: <1ms
- Первая проверка: ~200ms в background thread

#### 3. Vault API latency

**Проблема:** Vault requests ~300-500ms → slow startup.

**Решение: Parallel requests + aggressive caching**

```python
class VaultClient:
    def __init__(self, url: str, token: str):
        self.client = hvac.Client(url=url, token=token)
        self._secret_cache: Dict[str, Tuple[str, datetime]] = {}
        self._cache_ttl = timedelta(hours=12)  # Кэшировать 12 часов
    
    async def read_secret_batch(self, paths: List[str]) -> Dict[str, str]:
        """
        Загрузить multiple секретов параллельно.
        
        Производительность: N секретов за время 1 запроса (parallel).
        """
        # Разделить на cached и uncached
        results = {}
        uncached_paths = []
        
        for path in paths:
            if path in self._secret_cache:
                value, timestamp = self._secret_cache[path]
                if datetime.now() - timestamp < self._cache_ttl:
                    results[path] = value
                    continue
            
            uncached_paths.append(path)
        
        if not uncached_paths:
            logger.debug("Все секреты из кэша", count=len(paths))
            return results
        
        # Загрузить uncached секреты параллельно
        logger.info(
            "Загрузка секретов из Vault",
            cached=len(results),
            uncached=len(uncached_paths),
        )
        
        tasks = [
            asyncio.create_task(self._read_secret_async(path))
            for path in uncached_paths
        ]
        
        uncached_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for path, result in zip(uncached_paths, uncached_results):
            if isinstance(result, Exception):
                logger.error("Ошибка загрузки секрета", path=path, error=str(result))
                continue
            
            results[path] = result
            self._secret_cache[path] = (result, datetime.now())
        
        return results
    
    async def _read_secret_async(self, path: str) -> str:
        """Асинхронная загрузка секрета."""
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            self.client.secrets.kv.v2.read_secret_version,
            path,
        )
        
        return response['data']['data']['value']
```

**Результат:**
- 10 секретов: ~500ms вместо 5 секунд (parallel load)
- Повторные запросы: <1ms (кэш 12 часов)
- Graceful degradation при Vault failures (используется кэш)

#### 4. Hot reload cascade problem

**Проблема:** Hot reload → все компоненты reload одновременно → spike latency.

**Решение: Staged reload with priorities**

```python
class ConfigManager:
    async def _publish_config_updated(
        self,
        old_config: SystemConfig,
        new_config: SystemConfig,
    ):
        """
        Публиковать CONFIG_UPDATED с staged reload.
        """
        # Вычислить diff
        diff = self._compute_diff(old_config, new_config)
        
        # Определить приоритеты reload
        reload_priorities = self._compute_reload_priorities(diff)
        
        # Staged публикация по приоритетам
        for priority in ["critical", "high", "normal", "low"]:
            components = reload_priorities.get(priority, [])
            if not components:
                continue
            
            await self.event_bus.publish(Event(
                event_type="CONFIG_UPDATED",
                priority=Priority[priority.capitalize()],
                source="config_manager",
                payload={
                    "old_version": old_config.version,
                    "new_version": new_config.version,
                    "changed_sections": list(diff.keys()),
                    "reload_priority": priority,
                    "components": components,
                    "diff": diff,
                },
            ))
            
            # Delay между приоритетами (избежать spike)
            if priority != "low":
                await asyncio.sleep(0.1)
        
        logger.info(
            "CONFIG_UPDATED опубликован в staged режиме",
            priorities=list(reload_priorities.keys()),
        )
    
    def _compute_reload_priorities(self, diff: Dict) -> Dict[str, List[str]]:
        """
        Определить приоритеты reload компонентов.
        
        CRITICAL: Risk limits изменены → Risk Engine
        HIGH: Strategy params → Strategy Manager
        NORMAL: System settings → Control Plane
        LOW: Logging levels → Logger
        """
        priorities = {
            "critical": [],
            "high": [],
            "normal": [],
            "low": [],
        }
        
        if "risk" in diff:
            priorities["critical"].append("risk_engine")
        
        if "strategies" in diff:
            priorities["high"].append("strategy_manager")
        
        if "exchanges" in diff:
            priorities["high"].append("execution_layer")
        
        if "system" in diff:
            priorities["normal"].append("control_plane")
        
        if "logging" in diff:
            priorities["low"].append("logger")
        
        return priorities
```

**Результат:**
- Reload распределен по времени (избежать spike)
- Критичные компоненты обновляются первыми
- Некритичные компоненты обновляются с задержкой

---

## 📊 ОБЯЗАТЕЛЬНЫЕ BENCHMARK ТЕСТЫ

### tests/benchmarks/bench_config_manager.py:

```python
import pytest
import asyncio
from pathlib import Path
from src.core.config_manager import ConfigManager
from src.core.config_schema import SystemConfig

@pytest.mark.benchmark
def test_config_access_latency(benchmark):
    """
    Benchmark доступа к конфигурации (hot path).
    
    Acceptance: <10μs median, <50μs p99
    """
    manager = ConfigManager()
    # Загрузить конфигурацию
    asyncio.run(manager.load_config(Path("config/test/config.yaml")))
    
    def access_config():
        # Типичный hot path: получить risk limit
        value = manager.get("risk.base_r_percent")
        return value
    
    result = benchmark(access_config)
    
    # Assertions
    assert result is not None
    # Benchmark автоматически проверит latency

@pytest.mark.benchmark
def test_nested_access_cached(benchmark):
    """
    Benchmark кэшированного доступа к вложенным значениям.
    
    Acceptance: <5μs (кэш hit)
    """
    manager = ConfigManager()
    asyncio.run(manager.load_config(Path("config/test/config.yaml")))
    
    # Warm up cache
    manager.get("exchanges.0.name")
    
    def cached_access():
        return manager.get("exchanges.0.name")
    
    benchmark(cached_access)

@pytest.mark.benchmark
async def test_hot_reload_latency():
    """
    Benchmark полного hot reload цикла.
    
    Acceptance: <1s (signature + validation + reload + event)
    """
    manager = ConfigManager()
    config_path = Path("config/test/config.yaml")
    
    # Initial load
    await manager.load_config(config_path)
    
    # Measure hot reload
    start = asyncio.get_event_loop().time()
    await manager.reload_config(config_path)
    end = asyncio.get_event_loop().time()
    
    reload_time = end - start
    
    assert reload_time < 1.0, f"Hot reload took {reload_time}s > 1s"
    
    # Check latency breakdown
    metrics = manager.get_metrics()
    assert metrics["signature_verification_ms"] < 200
    assert metrics["schema_validation_ms"] < 50
    assert metrics["event_publish_ms"] < 100

@pytest.mark.benchmark
async def test_vault_parallel_load():
    """
    Benchmark параллельной загрузки секретов из Vault.
    
    Acceptance: 10 секретов < 1s (параллельно)
    """
    vault = VaultClient(url="http://vault:8200", token="test_token")
    
    paths = [f"secret/data/test/secret_{i}" for i in range(10)]
    
    start = asyncio.get_event_loop().time()
    secrets = await vault.read_secret_batch(paths)
    end = asyncio.get_event_loop().time()
    
    load_time = end - start
    
    assert len(secrets) == 10
    assert load_time < 1.0, f"Parallel load took {load_time}s > 1s"

@pytest.mark.benchmark
def test_schema_validation_performance(benchmark):
    """
    Benchmark Pydantic schema validation.
    
    Acceptance: <50ms для полной конфигурации
    """
    yaml_data = {
        "version": "v2.0.0",
        "environment": "test",
        "risk": {
            "base_r_percent": 0.02,
            "max_r_per_trade": 0.05,
            "max_drawdown_hard": 0.20,
            "max_drawdown_soft": 0.15,
            "correlation_limit": 0.7,
        },
        "exchanges": [
            {
                "name": "bybit",
                "enabled": True,
                "api_key_vault_path": "secret/data/test/api_key",
                "api_secret_vault_path": "secret/data/test/secret",
                "rate_limits": {"orders_per_second": 10},
            }
        ],
        "strategies": [],
        "system": {},
    }
    
    def validate():
        config = SystemConfig.parse_obj(yaml_data)
        return config
    
    result = benchmark(validate)
    assert result.version == "v2.0.0"

@pytest.mark.benchmark
async def test_config_update_propagation():
    """
    Benchmark распространения CONFIG_UPDATED события.
    
    Acceptance: все подписчики получили < 500ms
    """
    manager = ConfigManager()
    event_bus = manager.event_bus
    
    # Создать 10 подписчиков
    subscribers = [event_bus.subscribe("CONFIG_UPDATED") for _ in range(10)]
    
    # Hot reload
    start = asyncio.get_event_loop().time()
    await manager.reload_config(Path("config/test/config.yaml"))
    
    # Дождаться получения всеми подписчиками
    events_received = 0
    async def wait_for_events():
        nonlocal events_received
        for sub in subscribers:
            event = await asyncio.wait_for(sub.recv(), timeout=1.0)
            events_received += 1
    
    await wait_for_events()
    end = asyncio.get_event_loop().time()
    
    propagation_time = end - start
    
    assert events_received == 10
    assert propagation_time < 0.5, f"Propagation took {propagation_time}s > 500ms"
```

**Acceptance Criteria для benchmarks:**
```
✅ config_access: median <10μs, p99 <50μs
✅ nested_access_cached: <5μs (кэш hit)
✅ hot_reload: <1s (полный цикл)
✅ schema_validation: <50ms
✅ vault_parallel_load: 10 секретов <1s
✅ config_update_propagation: все подписчики <500ms
```

### Integration test (hot reload под нагрузкой):

```python
@pytest.mark.integration
async def test_hot_reload_under_load():
    """
    Hot reload во время активного использования конфигурации.
    
    Сценарий:
    1. 100 concurrent читателей конфигурации
    2. Hot reload во время чтения
    3. Проверить что никто не получил inconsistent состояние
    """
    manager = ConfigManager()
    await manager.load_config(Path("config/test/config.yaml"))
    
    stop_flag = False
    inconsistencies = []
    
    async def reader(reader_id: int):
        """Постоянно читать конфигурацию."""
        while not stop_flag:
            try:
                # Читать два связанных значения
                base_r = manager.get("risk.base_r_percent")
                max_r = manager.get("risk.max_r_per_trade")
                
                # Проверить invariant: base_r <= max_r
                if base_r > max_r:
                    inconsistencies.append({
                        "reader": reader_id,
                        "base_r": base_r,
                        "max_r": max_r,
                    })
                
                await asyncio.sleep(0.001)  # 1ms между чтениями
            except Exception as e:
                inconsistencies.append({"reader": reader_id, "error": str(e)})
    
    # Запустить 100 читателей
    readers = [asyncio.create_task(reader(i)) for i in range(100)]
    
    # Дать им поработать 100ms
    await asyncio.sleep(0.1)
    
    # Hot reload
    await manager.reload_config(Path("config/test/config_v2.yaml"))
    
    # Еще 100ms работы
    await asyncio.sleep(0.1)
    
    # Остановить читателей
    stop_flag = True
    await asyncio.gather(*readers)
    
    # Assertions
    assert len(inconsistencies) == 0, f"Обнаружено {len(inconsistencies)} несоответствий"
```

---

## ACCEPTANCE CRITERIA

### Schema
- [ ] SystemConfig с всеми полями
- [ ] Validators работают (drawdown, weights, etc.)
- [ ] extra="forbid" блокирует unknown fields
- [ ] Invalid configs rejected

### Signature Verification
- [ ] import_public_key() работает
- [ ] verify_file() проверяет подпись
- [ ] Tampering detected
- [ ] Invalid signature → RuntimeError

### Config Manager
- [ ] load_config() работает
- [ ] Schema validation integrated
- [ ] Signature verification integrated
- [ ] Vault secrets loading
- [ ] get() nested access работает
- [ ] hot_reload() работает
- [ ] rollback() работает
- [ ] Version history (10 versions)

### Testing
- [ ] Unit tests coverage >= 90%
- [ ] Integration test проходит

---

## 📤 ФОРМАТ ВЫДАЧИ

Для каждого файла:
1. Полный путь
2. Весь код
3. Header комментарий
4. "✅ filename READY"

В конце:
```
📦 GENERATED FILES:
- src/core/config_schema.py ✅
- src/core/signature_verifier.py ✅
- src/core/config_manager.py ✅
- src/core/config_watcher.py ✅
- config/dev/config.yaml ✅
- scripts/sign_config.py ✅
- tests/unit/test_config_schema.py ✅
- tests/unit/test_signature_verifier.py ✅
- tests/integration/test_config_full_flow.py ✅

🧪 NEXT STEPS:
1. pytest tests/unit/test_config_schema.py -v
2. pytest tests/unit/test_signature_verifier.py -v
3. pytest tests/integration/ -v
4. python scripts/sign_config.py config/dev/config.yaml --key-id YOUR_KEY
```

---

## ✅ ПРОВЕРКА РЕЗУЛЬТАТА

### 1. Schema Validation
```bash
pytest tests/unit/test_config_schema.py -v
```
**Ожидаемо:** All tests pass

### 2. Signature Verification
```bash
pytest tests/unit/test_signature_verifier.py -v
```
**Ожидаемо:** All tests pass

### 3. Integration Test
```bash
pytest tests/integration/test_config_full_flow.py -v
```
**Ожидаемо:** Config loads, validates, signature checks

### 4. Type Checking
```bash
mypy src/core/config_*.py --strict
```
**Ожидаемо:** No errors

### 5. Sign Example Config
```bash
# Generate GPG key first
gpg --gen-key

# Sign config
python scripts/sign_config.py config/dev/config.yaml --key-id YOUR_KEY_ID
```
**Ожидаемо:** `config.yaml.sig` created

---

## ВАЖНО

1. **НЕ используйте TODO**
2. **Decimal для финансовых значений** (не float)
3. **Validators проверяют бизнес-логику**
4. **Invalid signature → KillSwitch**
5. **Vault errors → RuntimeError**
6. **Version history limited to 10**
7. **Debounce file watching (1 sec)**

---

**Успехов в реализации Config Manager!** 🚀
