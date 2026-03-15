# Infisical Setup Guide

## Обзор

CRYPTOTEHNOLOG использует **Infisical** для безопасного хранения секретов:
- API ключи бирж (Bybit, OKX, Binance)
- Токены Telegram ботов
- Пароли баз данных
- JWT secrets

## Архитектура безопасности

```
┌─────────────────────────────────────────────────────────┐
│  Developer Workstation (air-gapped dev environment)      │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Docker Network: infisical_internal (internal)  │   │
│  │                                                   │   │
│  │  ┌─────────────┐  ┌──────────┐  ┌───────────┐  │   │
│  │  │  Infisical  │  │PostgreSQL│  │   Redis   │  │   │
│  │  │   :8080     │  │  :5432   │  │   :6379   │  │   │
│  │  │ 127.0.0.1   │  │127.0.0.1 │  │127.0.0.1  │  │   │
│  │  └─────────────┘  └──────────┘  └───────────┘  │   │
│  │                                                   │   │
│  │  🔒 Все данные зашифрованы на уровне volume     │   │
│  └──────────────────────────────────────────────────┘   │
│                           ↑                              │
│  CRYPTOTEHNOLOG ──────────┘ (localhost only)            │
│                                                          │
│  Machine Identity:                                       │
│  ✅ Генерируется локально                               │
│  ✅ Хранится в secrets/infisical-token                │
│  ✅ Не передаётся по сети                               │
└─────────────────────────────────────────────────────────┘
```

## Быстрый старт

### 1. Запуск Infisical

**Windows:**
```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_infisical.ps1
```

**Linux/Mac:**
```bash
chmod +x scripts/setup_infisical.sh
./scripts/setup_infisical.sh
```

Скрипт автоматически:
- Генерирует безопасные ключи (используя `secrets.token_hex`)
- Создаёт `.env.infisical` файл
- Запускает Docker контейнеры
- Проверяет готовность

### 2. Настройка в браузере

1. Откройте http://127.0.0.1:8080
2. Создайте admin аккаунт
3. Создайте проект: `crypto-trading`
4. Создайте environments:
   - `development`
   - `staging`
   - `production`

### 3. Добавление секретов

Создайте следующие secrets в каждом environment:

```
/crypto/exchange/bybit/api_key
/crypto/exchange/bybit/api_secret
/crypto/exchange/bybit/testnet (true/false)

/crypto/exchange/okx/api_key
/crypto/exchange/okx/api_secret
/crypto/exchange/okx/passphrase

/crypto/exchange/binance/api_key
/crypto/exchange/binance/api_secret

/telegram/bot_token
/telegram/chat_id

/database/postgres/password
/database/redis/password
```

### 4. Machine Identity (для бота)

1. В Infisical UI: Settings → Machine Identities
2. Создайте identity: `crypto-bot`
3. Скопируйте токен в файл `secrets/infisical-token`:
   ```bash
   echo "your-machine-identity-token" > secrets/infisical-token
   chmod 600 secrets/infisical-token
   ```

## Конфигурация Python

### Использование по умолчанию (локальный Infisical)

```python
from cryptotechnolog.config.providers import InfisicalConfigProvider

# Автоматически читает из локального Infisical
provider = InfisicalConfigProvider()
secrets = await provider.load("")
```

### Использование Machine Identity

```python
provider = InfisicalConfigProvider(
    use_machine_identity=True,
    project_id="crypto-trading",
    environment="production"
)
```

### Cloud Infisical (fallback)

```python
provider = InfisicalConfigProvider(
    local_url="https://api.infisical.com",
    fallback_to_env=True
)
```

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `INFISICAL_TOKEN` | Токен доступа | - |
| `INFISICAL_PROJECT_ID` | ID проекта | - |
| `INFISICAL_URL` | URL Infisical | http://127.0.0.1:8080 |

## Fallback логика

1. **Сначала**: Пробует локальный Infisical (`http://127.0.0.1:8080`)
2. **Если недоступен**: Пробует cloud Infisical (`https://api.infisical.com`)
3. **Если ничего не работает**: Ошибка с инструкцией запуска

## Безопасность

### Проверка localhost-only

```bash
# Должно работать (localhost)
curl http://127.0.0.1:8080/api/status

# НЕ должно работать (внешний IP)
curl http://$(hostname -I | awk '{print $1}'):8080/api/status
# Ожидаем: Connection refused
```

### Backup

Регулярно бекапьте:
- `.env.infisical` файл
- Docker volumes: `infisical_postgres`, `infisical_redis`

```bash
# Backup volumes
docker run --rm -v cryptotehnolog_infisical_postgres:/data -v $(pwd)/backups:/backup alpine tar czf /backup/infisical-pg-$(date +%Y%m%d).tar.gz /data
```

## Troubleshooting

### Infisical не запускается

```bash
# Проверка логов
docker-compose -f docker-compose-infisical.yml logs -f

# Проверка портов
netstat -ano | findstr :8080
```

### Ошибка подключения

```python
# Проверка URL
provider = InfisicalConfigProvider()
print(provider.get_url())  # Должен показать текущий URL
print(provider.is_local())  # True для локального
```

### Machine Identity не работает

```bash
# Проверьте файл
cat secrets/infisical-token

# Проверьте права доступа
ls -la secrets/infisical-token
# Должно быть: -rw-------
```

## Альтернативы

### HashiCorp Vault

Если нужен более enterprise-grade solution:

1. Замените `docker-compose-infisical.yml` на Vault
2. Обновите `InfisicalConfigProvider` на `VaultConfigProvider`
3. Используйте KV v2 secrets engine

###env файлы (только для разработки)

Для быстрой разработки без Infisical:

```bash
# Создайте .env файл
cp .env.example .env
# Заполните значения
```

## Следующие шаги

- [x] Запустить Infisical локально
- [ ] Настроить secrets в Infisical
- [ ] Создать Machine Identity
- [ ] Протестировать подключение из Python
- [ ] Запустить CRYPTOTEHNOLOG с Infisical
