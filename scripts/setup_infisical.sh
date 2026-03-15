# ==================== Infisical Setup Script ====================
# Generates secure secrets and starts Infisical Docker Compose
# 
# Usage:
#   chmod +x scripts/setup_infisical.sh
#   ./scripts/setup_infisical.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env.infisical"

echo "🔐 CRYPTOTEHNOLOG Infisical Setup"
echo "=================================="

# Check if running on Linux/Mac (not Windows)
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    echo "❌ This script requires Linux or macOS"
    echo "   For Windows, use setup_infisical.ps1"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

# Generate secrets using Python secrets module (more secure than openssl)
echo "📝 Generating secure secrets..."

DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_hex(32))")
ENCRYPTION_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
AUTH_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Create .env file
echo "📄 Creating .env.infisical file..."
cat > "$ENV_FILE" << EOF
# Infisical Secrets - DO NOT COMMIT TO VERSION CONTROL!
# Generated automatically on $(date)

# Database password (32 bytes hex = 64 characters)
DB_PASSWORD=$DB_PASSWORD

# Encryption key for data at rest (32 bytes hex = 64 characters)
ENCRYPTION_KEY=$ENCRYPTION_KEY

# Auth secret for JWT tokens (32 bytes hex = 64 characters)
AUTH_SECRET=$AUTH_SECRET
EOF

# Set strict permissions (owner read/write only)
chmod 600 "$ENV_FILE"

echo "✅ Secrets generated and saved to .env.infisical"
echo "   File permissions: 600 (owner only)"

# Source the env file for docker-compose
export $(cat "$ENV_FILE" | grep -v '^#' | xargs)

# Start Infisical
echo "🚀 Starting Infisical Docker Compose..."
cd "$PROJECT_ROOT"
docker-compose -f docker-compose-infisical.yml up -d

# Wait for Infisical to be ready
echo "⏳ Waiting for Infisical to initialize..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://127.0.0.1:8080/api/status > /dev/null 2>&1; then
        echo "✅ Infisical is ready!"
        echo ""
        echo "========================================"
        echo "🎉 Infisical setup complete!"
        echo "========================================"
        echo ""
        echo "📍 Access Infisical UI:"
        echo "   http://127.0.0.1:8080"
        echo ""
        echo "📁 Secrets file:"
        echo "   $ENV_FILE"
        echo ""
        echo "⚠️  IMPORTANT:"
        echo "   - NEVER commit .env.infisical to version control"
        echo "   - Add .env.infisical to .gitignore"
        echo "   - Backup this file securely"
        echo ""
        echo "🔧 Next steps:"
        echo "   1. Open http://127.0.0.1:8080"
        echo "   2. Create admin account"
        echo "   3. Create project: crypto-trading"
        echo "   4. Create environments: development, staging, production"
        echo "   5. Add secrets:"
        echo "      - /crypto/exchange/bybit/api_key"
        echo "      - /crypto/exchange/bybit/api_secret"
        echo "      - /telegram/bot_token"
        echo "   6. Create Machine Identity for bot access"
        echo ""
        exit 0
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "   Waiting... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

echo "❌ Infisical failed to start within expected time"
echo "   Check logs: docker-compose -f docker-compose-infisical.yml logs"
exit 1
