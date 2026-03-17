#!/bin/bash
# Скрипт для генерации Infisical токенов для сервисов
# Использование: ./scripts/generate_infisical_tokens.sh

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Генерация Infisical токенов для сервисов ===${NC}"

# URL Infisical (локальный или облачный)
INFISICAL_URL="${INFISICAL_URL:-http://127.0.0.1:8080}"

# Проверка наличия Client ID и Secret
if [ -z "$INFISICAL_CLIENT_ID" ] || [ -z "$INFISICAL_CLIENT_SECRET" ]; then
    echo -e "${RED}Ошибка: INFISICAL_CLIENT_ID и INFISICAL_CLIENT_SECRET должны быть установлены${NC}"
    echo "Экспортируйте переменные:"
    echo "  export INFISICAL_CLIENT_ID=your-client-id"
    echo "  export INFISICAL_CLIENT_SECRET=your-client-secret"
    exit 1
fi

# Функция для получения токена
get_token() {
    local service_name=$1
    
    response=$(curl -s -X POST "$INFISICAL_URL/api/v1/auth/universal-auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"clientId\":\"$INFISICAL_CLIENT_ID\",\"clientSecret\":\"$INFISICAL_CLIENT_SECRET\"}")
    
    if echo "$response" | grep -q "accessToken"; then
        echo "$response" | grep -o '"accessToken":"[^"]*' | cut -d'"' -f4
    else
        echo -e "${RED}Ошибка получения токена для $service_name${NC}"
        echo "$response"
        exit 1
    fi
}

# Проверка доступности Infisical
echo -e "${YELLOW}Проверка доступности Infisical...${NC}"
if curl -s "$INFISICAL_URL/api/status" | grep -q "Ok"; then
    echo -e "${GREEN}Infisical доступен${NC}"
else
    echo -e "${RED}Infisical недоступен${NC}"
    exit 1
fi

# Генерация токенов для каждого сервиса
echo -e "${YELLOW}Генерация токенов...${NC}"

# Основной сервис
INFISICAL_TOKEN_MAIN=$(get_token "main")
echo "INFISICAL_TOKEN_MAIN=$INFISICAL_TOKEN_MAIN"

# Сохранение в .env файл
cat > .env.infisical.tokens << EOF
# Auto-generated Infisical tokens
# Не коммитить в git!

INFISICAL_TOKEN_MAIN=$INFISICAL_TOKEN_MAIN
EOF

echo -e "${GREEN}Токены сгенерированы и сохранены в .env.infisical.tokens${NC}"
echo "Используйте: source .env.infisical.tokens перед запуском docker-compose"
