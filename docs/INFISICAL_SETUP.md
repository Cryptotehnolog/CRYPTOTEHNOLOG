# Infisical Setup Guide

## Что такое Infisical?

Infisical - это платформа для управления секретами (API ключи, пароли, токены и т.д.) с открытым исходным кодом.

### Преимущества:
- ✅ Бесплатный Cloud Tier (до 5 проектов, 50 секретов)
- ✅ E2E шифрование
- ✅ Современный UI
- ✅ SDK для Python/Rust/Node.js
- ✅ GitOps ready
- ✅ Self-hosted (можно развернуть на своем сервере)

---

## Быстрый старт

### 1. Создание аккаунта

1. Перейдите на https://infisical.com
2. Нажмите **"Sign Up"**
3. Зарегистрируйтесь через GitHub (рекомендуется) или Email

### 2. Создание проекта

1. После входа нажмите **"Create Project"**
2. Заполните:
   - **Project Name**: `CRYPTOTEHNOLOG`
   - **Project Description**: `Institutional-Grade Crypto Trading Platform`
3. Нажмите **"Create Project"**

### 3. Получение Project ID

1. Откройте созданный проект
2. Посмотрите на URL:
   ```
   https://app.infisical.com/project/ВАШ_PROJECT_ID/overview
   ```
3. Скопируйте `ВАШ_PROJECT_ID` (например: `9a8b7c6d-5e4f-3a2b-1c0d-9e8f7a6b5c4d`)

### 4. Генерация Access Token

1. Нажмите на ваш аватар (правый верхний угол)
2. Перейдите в **"Access Tokens"**
3. Нажмите **"Generate Token"**
4. Заполните:
   - **Token Name**: `CRYPTOTEHNOLOG-Dev`
   - **Expiration**: `90 days` (или `Never`)
   - **Scope**: `Read & Write`
5. Нажмите **"Generate"**
6. **Скопируйте токен** (появится только один раз!)

### 5. Настройка окружений (Environments)

1. В проекте перейдите в раздел **"Secrets"**
2. Убедитесь, что созданы среды:
   - `Dev` (для разработки)
   - `Prod` (для производства)

Если нет, создайте их через **"Create Environment"**

---

## Добавление секретов

### Через Web UI

1. Перейдите в проект -> **"Secrets"**
2. Выберите среду (например, `Dev`)
3. Нажмите **"Create Secret"**
4. Добавьте секреты:

#### База данных
```
POSTGRES_USER=bot_user
POSTGRES_PASSWORD=bot_password_dev
POSTGRES_DB=trading_dev
```

#### Exchange API (тестовые ключи)
```
BYBIT_API_KEY=your_bybit_api_key
BYBIT_API_SECRET=your_bybit_api_secret
BYBIT_TESTNET=true

OKX_API_KEY=your_okx_api_key
OKX_API_SECRET=your_okx_api_secret
OKX_PASSPHRASE=your_okx_passphrase
OKX_TESTNET=true

BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_api_secret
BINANCE_TESTNET=true
```

### Через CLI

Установка CLI:
```bash
npm install -g infisical
```

Импорт секретов:
```bash
# Из файла
infisical import --env=dev --path=secrets.txt

# Из переменных окружения
infisical set POSTGRES_PASSWORD "bot_password_dev" --env=dev
```

---

## Настройка проекта

### Обновление .env файла

Создайте файл `.env` в корне проекта:

```env
# Infisical Configuration
INFISICAL_TOKEN=ваш_токен_от_шага_4
INFISICAL_ADDRESS=https://vault.infisical.com
INFISICAL_PROJECT_ID=ваш_project_id_от_шага_3
INFISICAL_ENVIRONMENT=dev

# Остальные настройки...
DEBUG=true
LOG_LEVEL=INFO
```

### Установка Python SDK

```bash
pip install infisical
```

---

## Использование в коде

### Пример 1: Получение секрета

```python
from src.config.infisical_client import get_secret, infisical_manager

# Получить секрет
api_key = get_secret("BYBIT_API_KEY")

# Или через менеджер
api_key = infisical_manager.get_secret("BYBIT_API_KEY")
```

### Пример 2: Получение всех секретов

```python
from src.config.infisical_client import get_all_secrets

all_secrets = get_all_secrets()
print(all_secrets)
```

### Пример 3: Установка секрета

```python
from src.config.infisical_client import infisical_manager

infisical_manager.set_secret("NEW_SECRET", "secret_value")
```

### Пример 4: Проверка доступности

```python
from src.config.infisical_client import infisical_manager

if infisical_manager.is_available():
    print("✅ Infisical доступен")
else:
    print("⚠️  Infisical недоступен, используются переменные окружения")
```

---

## Интеграция с Settings

Секреты автоматически загружаются в настройки:

```python
from src.config.settings import settings

# Секреты доступны через settings
print(settings.bybit_api_key)
print(settings.postgres_password)
```

Приоритет загрузки:
1. Переменные окружения (.env)
2. Infisical
3. Значения по умолчанию

---

## Структура папок и секретов

### Требуемые папки в Infisical

Создайте следующие папки в проекте:

| Папка | Назначение | Секреты |
|-------|------------|---------|
| `database` | PostgreSQL и Redis | POSTGRES_*, REDIS_* |
| `exchanges/binance` | Binance API | BINANCE_API_KEY, BINANCE_API_SECRET, BINANCE_TESTNET |
| `exchanges/bybit` | Bybit API | BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_TESTNET |
| `exchanges/okx` | OKX API | OKX_API_KEY, OKX_API_SECRET, OKX_PASSPHRASE, OKX_TESTNET |
| `observability` | Мониторинг | LOG_LEVEL, LOG_FORMAT, PROMETHEUS_PORT, DASHBOARD_* |
| `security` | Безопасность | INFISICAL_*, VAULT_* |
| `api` | Внешние API | NEWS_API_KEY, TELEGRAM_BOT_TOKEN, DISCORD_WEBHOOK_URL |
| `webhooks` | Webhook URLs | ALERT_WEBHOOK_URL, TRADE_WEBHOOK_URL, RISK_WEBHOOK_URL |
| `storage` | Облачное хранилище | AWS_*, GCP_* |
| `monitoring` | Внешний мониторинг | SENTRY_DSN, DATADOG_*, PAGERDUTY_API_KEY |
| `trading` | Торговые параметры | BASE_R_PERCENT, MAX_R_PER_TRADE, MAX_PORTFOLIO_R |
| `environment` | Настройки окружения | ENVIRONMENT, DEBUG, TIMEZONE, CURRENCY |

### Полный список секретов

Полный список всех секретов с описаниями находится в файле:
```
config/infisical_secrets.yaml
```

---

## Автоматизация работы с секретами

### Скрипты проекта

#### 1. Загрузка секретов из Infisical в .env

```bash
# Установите переменные окружения
export INFISICAL_TOKEN="your_token_here"
export INFISICAL_PROJECT_ID="your_project_id_here"
export INFISICAL_ENVIRONMENT="dev"

# Запустите скрипт загрузки
python scripts/load_secrets_from_infisical.py
```

Что делает скрипт:
- ✅ Подключается к Infisical
- ✅ Загружает все секреты из всех папок
- ✅ Генерирует файл `.env`
- ✅ Создает резервную копию `.env.backup`
- ✅ Использует значения по умолчанию если секрет не найден

#### 2. Загрузка секретов в Infisical (для начальной настройки)

```bash
# Установите переменные окружения
export INFISICAL_TOKEN="your_token_here"
export INFISICAL_PROJECT_ID="your_project_id_here"
export INFISICAL_ENVIRONMENT="dev"

# Запустите скрипт загрузки
python scripts/upload_secrets_to_infisical.py
```

Что делает скрипт:
- ✅ Читает конфигурацию из `config/infisical_secrets.yaml`
- ✅ Загружает секреты со значениями по умолчанию в Infisical
- ✅ Пропускает секреты без значений по умолчанию
- ✅ Показывает статистику загрузки

---

## Интеграция с CI/CD

### GitHub Actions

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # Установка Python
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      # Установка зависимостей
      - name: Install dependencies
        run: |
          pip install infisical pyyaml

      # Загрузка секретов из Infisical
      - name: Load secrets from Infisical
        run: |
          export INFISICAL_TOKEN="${{ secrets.INFISICAL_TOKEN }}"
          export INFISICAL_PROJECT_ID="${{ secrets.INFISICAL_PROJECT_ID }}"
          export INFISICAL_ENVIRONMENT="dev"
          python scripts/load_secrets_from_infisical.py

      # Запуск тестов
      - name: Run tests
        run: pytest tests/
```

### Добавление секретов в GitHub

1. Перейдите в репозиторий GitHub
2. Settings → Secrets and variables → Actions
3. Добавьте:
   - `INFISICAL_TOKEN` - Service Token из Infisical
   - `INFISICAL_PROJECT_ID` - Project ID из Infisical
   - `INFISICAL_ENVIRONMENT` - Окружение (dev/prod)

---

## Безопасность

### Best Practices

1. ✅ Никогда не коммитите `.env` файл
2. ✅ Используйте разные токены для dev/prod
3. ✅ Установите срок действия токенов (expiration)
4. ✅ Ограничьте доступ к токенам
5. ✅ Используйте IP whitelist (если доступно)
6. ✅ Регулярно ротируйте секреты
7. ✅ Используйте разные среды (dev, staging, prod)

### Мониторинг

Infisical предоставляет логи доступа:
1. Перейдите в проект
2. Settings -> Activity Logs
3. Смотрите кто и когда обращался к секретам

---

## Устранение проблем

### Проблема: "INFISICAL_TOKEN not set"

**Решение:**
1. Проверьте `.env` файл
2. Убедитесь, что токен скопирован правильно
3. Перезагрузите терминал после изменения `.env`

### Проблема: "Failed to initialize Infisical client"

**Решение:**
1. Проверьте подключение к интернету
2. Убедитесь, что токен и project_id верные
3. Проверьте, что SDK установлен: `pip install infisical`

### Проблема: "Secret not found"

**Решение:**
1. Проверьте, что секрет существует в Infisical
2. Убедитесь, что выбрана правильная среда (env)
3. Проверьте имя секрета (регистрозависимое)

### Проблема: "Falling back to environment variables"

Это не ошибка! Это означает, что:
- Infisical недоступен
- Или токен не настроен
- Или SDK не установлен

Система автоматически использует переменные окружения.

---

## Дополнительные ресурсы

- [Infisical Documentation](https://infisical.com/docs)
- [Python SDK](https://infisical.com/docs/sdk/python)
- [CLI Documentation](https://infisical.com/docs/cli/overview)
- [GitHub Repository](https://github.com/Infisical/infisical)

---

## Поддержка

Если возникли вопросы:
1. Проверьте логи приложения
2. Посмотрите Activity Logs в Infisical
3. Обратитесь к документации
4. Создайте issue в репозитории проекта
