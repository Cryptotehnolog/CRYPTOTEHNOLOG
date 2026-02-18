# ==================== CRYPTOTEHNOLOG Infisical Client ====================
# Client for managing secrets via Infisical

import os

try:
    from infisical import Client as InfisicalClient

    INFISICAL_AVAILABLE = True
except ImportError:
    INFISICAL_AVAILABLE = False


class InfisicalSecretsManager:
    """
    Менеджер секретов Infisical

    Управляет секретами через Infisical платформу.
    Если Infisical недоступен, использует переменные окружения.
    """

    def __init__(
        self,
        token: str | None = None,
        project_id: str | None = None,
        environment: str = "dev",
    ):
        """
        Инициализация клиента Infisical

        Args:
            token: Infisical API токен
            project_id: ID проекта в Infisical
            environment: Среда (dev, prod, etc.)
        """
        self.token = token or os.getenv("INFISICAL_TOKEN")
        self.project_id = project_id or os.getenv("INFISICAL_PROJECT_ID")
        self.environment = environment or os.getenv("INFISICAL_ENVIRONMENT", "dev")

        self.client = None

        # Инициализируем клиент только если Infisical доступен и токен предоставлен
        if INFISICAL_AVAILABLE and self.token and self.project_id:
            try:
                self.client = InfisicalClient(
                    token=self.token,
                    project_id=self.project_id,
                    environment=self.environment,
                )
                print(f"✅ Infisical client initialized (environment: {self.environment})")
            except Exception as e:
                print(f"⚠️  Failed to initialize Infisical client: {e}")
                print("   Falling back to environment variables")
        elif not INFISICAL_AVAILABLE:
            print("⚠️  Infisical SDK not installed. Install with: pip install infisical")
            print("   Falling back to environment variables")
        elif not self.token:
            print("⚠️  INFISICAL_TOKEN not set. Falling back to environment variables")
        elif not self.project_id:
            print("⚠️  INFISICAL_PROJECT_ID not set. Falling back to environment variables")

    def get_secret(self, secret_name: str) -> str | None:
        """
        Получить секрет по имени

        Приоритет:
        1. Переменная окружения
        2. Infisical
        3. None

        Args:
            secret_name: Имя секрета

        Returns:
            Значение секрета или None
        """
        # Сначала проверяем переменные окружения
        env_value = os.getenv(secret_name)
        if env_value:
            return env_value

        # Затем пробуем получить из Infisical
        if self.client:
            try:
                secret = self.client.get_secret(secret_name)
                if secret:
                    return secret.value
            except Exception as e:
                print(f"⚠️  Failed to get secret '{secret_name}' from Infisical: {e}")

        return None

    def get_all_secrets(self) -> dict[str, str]:
        """
        Получить все секреты

        Возвращает секреты из Infisical и переменных окружения.

        Returns:
            Словарь секретов
        """
        secrets = {}

        # Получаем секреты из Infisical
        if self.client:
            try:
                infisical_secrets = self.client.get_all_secrets()
                for secret in infisical_secrets:
                    secrets[secret.name] = secret.value
            except Exception as e:
                print(f"⚠️  Failed to get secrets from Infisical: {e}")

        # Добавляем переменные окружения (переопределяют Infisical)
        env_secrets = {
            key: value
            for key, value in os.environ.items()
            if key.isupper() and not key.startswith("_")
        }
        secrets.update(env_secrets)

        return secrets

    def set_secret(self, secret_name: str, secret_value: str) -> bool:
        """
        Установить секрет

        Args:
            secret_name: Имя секрета
            secret_value: Значение секрета

        Returns:
            True если успешно, иначе False
        """
        if self.client:
            try:
                self.client.set_secret(secret_name, secret_value)
                print(f"✅ Secret '{secret_name}' set in Infisical")
                return True
            except Exception as e:
                print(f"⚠️  Failed to set secret '{secret_name}': {e}")
                return False
        else:
            print("⚠️  Infisical client not available. Secret not set.")
            return False

    def delete_secret(self, secret_name: str) -> bool:
        """
        Удалить секрет

        Args:
            secret_name: Имя секрета

        Returns:
            True если успешно, иначе False
        """
        if self.client:
            try:
                self.client.delete_secret(secret_name)
                print(f"✅ Secret '{secret_name}' deleted from Infisical")
                return True
            except Exception as e:
                print(f"⚠️  Failed to delete secret '{secret_name}': {e}")
                return False
        else:
            print("⚠️  Infisical client not available. Secret not deleted.")
            return False

    def is_available(self) -> bool:
        """
        Проверить доступность Infisical

        Returns:
            True если Infisical доступен, иначе False
        """
        return self.client is not None

    def reload(self) -> None:
        """
        Перезагрузить клиент Infisical

        Полезно после изменения токена или project_id.
        """
        if INFISICAL_AVAILABLE and self.token and self.project_id:
            try:
                self.client = InfisicalClient(
                    token=self.token,
                    project_id=self.project_id,
                    environment=self.environment,
                )
                print("✅ Infisical client reloaded")
            except Exception as e:
                print(f"⚠️  Failed to reload Infisical client: {e}")


# ==================== Глобальный экземпляр ====================
# Создается при импорте модуля
infisical_manager = InfisicalSecretsManager()


# ==================== Удобные функции ====================
def get_secret(secret_name: str, default: str | None = None) -> str | None:
    """
    Удобная функция для получения секрета

    Args:
        secret_name: Имя секрета
        default: Значение по умолчанию

    Returns:
        Значение секрета или default
    """
    value = infisical_manager.get_secret(secret_name)
    return value if value is not None else default


def get_all_secrets() -> dict[str, str]:
    """
    Удобная функция для получения всех секретов

    Returns:
        Словарь секретов
    """
    return infisical_manager.get_all_secrets()
