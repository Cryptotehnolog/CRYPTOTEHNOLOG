#!/usr/bin/env python3
# ==================== CRYPTOTEHNOLOG Load Secrets from Infisical ====================
# Скрипт для загрузки секретов из Infisical в .env файл

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


def fetch_secrets_from_infisical(client: InfisicalClient, folders: list) -> dict:
    """
    Получить все секреты из Infisical

    Args:
        client: Infisical клиент
        folders: Список папок для загрузки

    Returns:
        Словарь секретов {имя: значение}
    """
    secrets = {}

    for folder in folders:
        folder_name = folder["folder"]
        print(f"📂 Загрузка секретов из папки: {folder_name}")

        for secret_config in folder.get("secrets", []):
            secret_name = secret_config["name"]

            try:
                # Получаем секрет из Infisical
                secret = client.get_secret(secret_name)

                if secret and secret.value:
                    secrets[secret_name] = secret.value
                    print(f"  ✅ {secret_name}")
                else:
                    # Используем значение по умолчанию
                    default = secret_config.get("default", "")
                    if default:
                        secrets[secret_name] = default
                        print(f"  ⚠️  {secret_name} (используется значение по умолчанию)")
                    else:
                        print(f"  ❌ {secret_name} (не найден и нет значения по умолчанию)")

            except Exception as e:
                # Если секрет не найден, используем значение по умолчанию
                default = secret_config.get("default", "")
                if default:
                    secrets[secret_name] = default
                    print(f"  ⚠️  {secret_name} (ошибка: {e}, используется значение по умолчанию)")
                else:
                    print(f"  ❌ {secret_name} (ошибка: {e})")

    return secrets


def write_env_file(secrets: dict, env_path: Path) -> None:
    """
    Записать секреты в .env файл

    Args:
        secrets: Словарь секретов
        env_path: Путь к .env файлу
    """
    with open(env_path, "w", encoding="utf-8") as f:
        # Заголовок
        f.write("# ==================== CRYPTOTEHNOLOG Environment Variables ====================\n")
        f.write("# Автоматически сгенерировано из Infisical\n")
        f.write(f"# Сгенерировано: {os.popen('date').read().strip()}\n")
        f.write("# ⚠️  НЕ КОММИТЬТЕ ЭТОТ ФАЙЛ В GIT!\n\n")

        # Записываем секреты
        for name, value in sorted(secrets.items()):
            # Экранируем спецсимволы
            if isinstance(value, str):
                value = value.replace('"', '\\"')
            f.write(f'{name}="{value}"\n')

        # Футер
        f.write("\n# ==================== Конец автоматически сгенерированных переменных ====================\n")

    print(f"\n✅ Секреты записаны в {env_path}")


def backup_existing_env(env_path: Path) -> None:
    """
    Создать резервную копию существующего .env файла

    Args:
        env_path: Путь к .env файлу
    """
    if env_path.exists():
        backup_path = env_path.with_suffix(".env.backup")
        import shutil

        shutil.copy2(env_path, backup_path)
        print(f"📦 Резервная копия создана: {backup_path}")


def main():
    """Главная функция"""
    print("=" * 70)
    print("CRYPTOTEHNOLOG - Загрузка секретов из Infisical")
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

    # Пути к файлам
    config_path = Path(__file__).parent.parent / "config" / "infisical_secrets.yaml"
    env_path = Path(__file__).parent.parent / ".env"

    # Проверяем существование конфигурации
    if not config_path.exists():
        print(f"❌ Конфигурация не найдена: {config_path}")
        sys.exit(1)

    # Создаем резервную копию
    backup_existing_env(env_path)

    # Загружаем конфигурацию
    print(f"\n📋 Загрузка конфигурации из {config_path}")
    folders = load_secrets_config(config_path)
    print(f"✅ Найдено {len(folders)} папок с секретами")

    # Создаем клиент Infisical
    print(f"\n🔐 Подключение к Infisical (environment: {environment})")
    client = get_infisical_client(token, project_id, environment)
    print("✅ Подключение успешно")

    # Получаем секреты
    print(f"\n📥 Загрузка секретов...")
    secrets = fetch_secrets_from_infisical(client, folders)

    # Записываем в .env
    print(f"\n📝 Запись секретов в {env_path}")
    write_env_file(secrets, env_path)

    print("\n" + "=" * 70)
    print("✅ Загрузка секретов завершена успешно!")
    print("=" * 70)
    print(f"\n📊 Статистика:")
    print(f"   - Загружено секретов: {len(secrets)}")
    print(f"   - Папок обработано: {len(folders)}")
    print(f"   - Файл .env обновлен: {env_path.absolute()}")


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
