#!/usr/bin/env python3
# ==================== CRYPTOTEHNOLOG Upload Secrets to Infisical ====================
# Скрипт для загрузки секретов в Infisical (для начальной настройки)

import os
import sys
from pathlib import Path

# Добавляем src в path
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

import yaml

try:
    from infisical import Client as InfisicalClient
    INFISICAL_AVAILABLE = True
except ImportError:
    INFISICAL_AVAILABLE = False
    print("❌ Infisical SDK не установлен. Установите: pip install infisical")
    sys.exit(1)


def load_secrets_config(config_path: Path) -> list:
    """
    Загрузить конфигурацию секретов из YAML файла

    Args:
        config_path: Путь к файлу конфигурации

    Returns:
        Список папок с секретами
    """
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_infisical_client(token: str, project_id: str, environment: str) -> InfisicalClient:
    """
    Создать клиент Infisical

    Args:
        token: Infisical токен
        project_id: ID проекта
        environment: Окружение

    Returns:
        Infisical клиент
    """
    return InfisicalClient(
        token=token,
        project_id=project_id,
        environment=environment,
    )


def upload_secrets_to_infisical(client: InfisicalClient, folders: list, environment: str) -> None:
    """
    Загрузить секреты в Infisical

    Args:
        client: Infisical клиент
        folders: Список папок с секретами
        environment: Окружение (dev/prod)
    """
    total_secrets = 0
    uploaded_secrets = 0
    skipped_secrets = 0

    for folder in folders:
        folder_name = folder["folder"]
        print(f"\n📂 Папка: {folder_name}")

        for secret_config in folder.get("secrets", []):
            secret_name = secret_config["name"]
            secret_description = secret_config.get("description", "")
            secret_default = secret_config.get("default", "")
            secret_required = secret_config.get("required", True)
            secret_env = secret_config.get("environment", "all")

            total_secrets += 1

            # Проверяем, подходит ли секрет для текущего окружения
            if secret_env != "all" and secret_env != environment:
                print(f"  ⏭️  {secret_name} (пропущен: не для окружения {environment})")
                skipped_secrets += 1
                continue

            # Проверяем, является ли секрет обязательным
            if secret_required and not secret_default:
                print(f"  ⚠️  {secret_name} (обязательный секрет без значения по умолчанию)")
                print(f"     📝 Добавьте вручную в Infisical")
                skipped_secrets += 1
                continue

            # Если есть значение по умолчанию, загружаем его
            if secret_default:
                try:
                    client.set_secret(secret_name, secret_default)
                    print(f"  ✅ {secret_name} (значение по умолчанию)")
                    uploaded_secrets += 1
                except Exception as e:
                    print(f"  ❌ {secret_name} (ошибка: {e})")
            else:
                print(f"  ⏭️  {secret_name} (пропущен: нет значения по умолчанию)")
                skipped_secrets += 1

    # Вывод статистики
    print("\n" + "=" * 70)
    print("📊 Статистика загрузки:")
    print(f"   - Всего секретов: {total_secrets}")
    print(f"   - Загружено: {uploaded_secrets}")
    print(f"   - Пропущено: {skipped_secrets}")
    print("=" * 70)


def main():
    """Главная функция"""
    print("=" * 70)
    print("CRYPTOTEHNOLOG - Загрузка секретов в Infisical")
    print("=" * 70)

    # Проверяем наличие Infisical SDK
    if not INFISICAL_AVAILABLE:
        print("❌ Infisical SDK не установлен")
        sys.exit(1)

    # Получаем переменные окружения для Infisical
    token = os.getenv("INFISICAL_TOKEN")
    project_id = os.getenv("INFISICAL_PROJECT_ID")
    environment = os.getenv("INFISICAL_ENVIRONMENT", "dev")

    if not token:
        print("❌ INFISICAL_TOKEN не установлен")
        print("   Установите: export INFISICAL_TOKEN=your_token")
        sys.exit(1)

    if not project_id:
        print("❌ INFISICAL_PROJECT_ID не установлен")
        print("   Установите: export INFISICAL_PROJECT_ID=your_project_id")
        sys.exit(1)

    # Путь к файлу конфигурации
    config_path = Path(__file__).parent.parent / "config" / "infisical_secrets.yaml"

    # Проверяем существование конфигурации
    if not config_path.exists():
        print(f"❌ Конфигурация не найдена: {config_path}")
        sys.exit(1)

    # Подтверждение
    print(f"\n⚠️  ВНИМАНИЕ: Секреты будут загружены в окружение: {environment}")
    print(f"   Project ID: {project_id}")
    response = input("\nПродолжить? (yes/no): ")
    if response.lower() not in ["yes", "y"]:
        print("❌ Отменено пользователем")
        sys.exit(0)

    # Загружаем конфигурацию
    print(f"\n📋 Загрузка конфигурации из {config_path}")
    folders = load_secrets_config(config_path)
    print(f"✅ Найдено {len(folders)} папок с секретами")

    # Создаем клиент Infisical
    print(f"\n🔐 Подключение к Infisical (environment: {environment})")
    client = get_infisical_client(token, project_id, environment)
    print("✅ Подключение успешно")

    # Загружаем секреты
    print(f"\n📤 Загрузка секретов в Infisical...")
    upload_secrets_to_infisical(client, folders, environment)

    print("\n" + "=" * 70)
    print("✅ Загрузка завершена!")
    print("=" * 70)
    print("\n📝 Примечание:")
    print("   - Загружены только секреты со значениями по умолчанию")
    print("   - Обязательные секреты без значений нужно добавить вручную")
    print("   - API ключи бирж нужно добавить вручную через веб-интерфейс Infisical")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
