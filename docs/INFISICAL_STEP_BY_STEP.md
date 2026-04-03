# Полное руководство по установке Infisical локально

## Шаг 1: Запустить Infisical через Docker

### Предварительные требования
- Docker Desktop установлен и запущен
- Доступ к интернету для загрузки образов (первый раз)

### Запуск

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_infisical.ps1
```

**Linux/Mac (Bash):**
```bash
bash scripts/setup_infisical.sh
```

**Что делает скрипт:**
1. Генерирует безопасные ключи для самого Infisical (DB_PASSWORD, ENCRYPTION_KEY, AUTH_SECRET)
2. Сохраняет их в файл `.env.infisical` (НЕ в git!)
3. Запускает Docker Compose с PostgreSQL, Redis и Infisical
4. Ждёт пока Infisical инициализируется
5. Проверяет здоровье сервиса

**Проверка запуска:**
```bash
curl http://127.0.0.1:8080/api/status
```

Должен вернуть JSON с статусом "ok".

---

## Шаг 2: Настроить Infisical через UI

### 2.1 Создать аккаунт администратора

1. Открой браузер: http://127.0.0.1:8080
2. Зарегистрируй новый аккаунт:
   - Email: твой email
   - Password: сложный пароль
3. Подтверди email (если требуется)

### 2.2 Создать проект

1. Нажми "Create Project"
2. Название: `crypto-trading`
3. Нажми "Create"

### 2.3 Создать окружения

Внутри проекта `crypto-trading`:

1. Перейди в "Environments"
2. Создай:
   - `development` (для разработки)
   - `staging` (для тестирования)
   - `production` (для боя)

### 2.4 Добавить секреты

Перейди в "Secrets" и добавь:

| Key | Value | Окружение |
|-----|-------|-----------|
| `BYBIT_API_KEY` | твой API ключ | development |
| `BYBIT_API_SECRET` | твой API secret | development |
| `TELEGRAM_BOT_TOKEN` | токен бота | development |
| `POSTGRES_PASSWORD` | пароль от БД | development |

**Структура секретов** (как в Infisical):
```
/crypto/exchange/bybit/api_key
/crypto/exchange/bybit/api_secret
/telegram/bot_token
/database/postgres/password
```

---

## Шаг 3: Создать Machine Identity

Machine Identity позволяет боту (Python скрипту) получать доступ к секретам без ввода пароля.

### 3.1 Создать Identity

1. В проекте `crypto-trading` перейди в "Machine Identities"
2. Нажми "Add Machine Identity"
3. Заполни:
   - Name: `crypto-bot`
   - Type: `Service`
   - Scopes: выбери все окружения

### 3.2 Создать токен

1. Нажми на созданный Identity
2. Перейди в "Tokens"
3. Нажми "Generate Token"
4. Выбери срок жизни: `1 year` (или меньше)
5. **Скопируй токен** - он показывается только один раз!

### 3.3 Сохранить токен локально

**Вариант А: В файл (рекомендуется)**
```bash
# Создай папку secrets/
mkdir -p secrets

# Сохрани токен
echo "твой_токен_здесь" > secrets/infisical-token
```

**Вариант Б: В .env.infisical**
```bash
# Добавь в .env.infisical
INFISICAL_TOKEN=твой_токен_здесь
```

---

## Шаг 4: Настроить Python код

### 4.1 Установить зависимости

```bash
pip install httpx python-dotenv
```

### 4.2 Проверить конфигурацию

Убедись что в `.env.infisical` есть:
```
DB_PASSWORD=...
ENCRYPTION_KEY=...
AUTH_SECRET=...
```

Важно:
- `DB_PASSWORD` здесь относится только к локальной инфраструктуре Infisical
- для runtime и integration tests платформы используется отдельная переменная `POSTGRES_PASSWORD`
- `Settings` в приложении читает именно `POSTGRES_PASSWORD`, а не `DB_PASSWORD`

ИЛИ токен:
```
INFISICAL_TOKEN=твой_токен
```

### 4.3 Проверить .gitignore

В файле `.gitignore` должны быть:
```
.env.infisical
secrets/
```

---

## Шаг 5: Протестировать подключение

### Тест 1: Проверка Infisical API

```bash
curl -H "Authorization: Bearer ТОКЕН" \
  "http://127.0.0.1:8080/v2/secrets?environment=development&projectId=ID_ПРОЕКТА"
```

### Тест 2: Python тест

```python
import asyncio
from cryptotechnolog.config.providers import InfisicalConfigProvider

async def test_infisical():
    try:
        provider = InfisicalConfigProvider(
            project_id="crypto-trading",
            environment="development",
            use_machine_identity=True  # Читает из secrets/infisical-token
        )
        
        print(f"Infisical URL: {provider.get_url()}")
        print(f"Is local: {provider.is_local()}")
        
        secrets = await provider.load("")
        print(f"Secrets loaded: {len(secrets)} items")
        
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test_infisical())
```

---

## Структура файлов после настройки

```
CRYPTOTEHNOLOG/
├── .env.infisical          # Секреты Infisical (НЕ в git!)
├── secrets/
│   └── infisical-token      # Токен Machine Identity (НЕ в git!)
├── docker-compose-infisical.yml
└── ...
```

---

## Управление Infisical

### Остановить
```bash
docker-compose -f docker-compose-infisical.yml down
```

### Запустить
```bash
docker-compose -f docker-compose-infisical.yml up -d
```

### Посмотреть логи
```bash
docker-compose -f docker-compose-infisical.yml logs -f infisical
```

### Обновить
```bash
docker-compose -f docker-compose-infisical.yml pull
docker-compose -f docker-compose-infisical.yml up -d
```

---

## Troubleshooting

### Ошибка: "Connection refused"
- Проверь что Docker запущен
- Проверь что порт 8080 не занят: `netstat -an | findstr 8080`

### Ошибка: "Invalid token"
- Токен истёк - создай новый в UI
- Неправильный project_id - проверь ID проекта

### Ошибка: "Database connection failed"
- Подожди 30 секунд после запуска
- Проверь логи: `docker-compose logs db`

---

## Следующие шаги

После настройки Infisical:

1. **Интеграция с Config Manager** - используй `InfisicalConfigProvider` для загрузки secrets
2. **Переменные окружения** - добавь `INFISICAL_PROJECT_ID=crypto-trading`
3. **CI/CD** - настрой secrets для GitHub Actions
