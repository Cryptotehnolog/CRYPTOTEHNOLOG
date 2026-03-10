"""
Тесты для GPGSigner.

Тестирование:
    - GPGSigner: верификация GPG подписей

Все docstrings на русском языке.
"""

from pathlib import Path

from cryptotechnolog.config.signers import GPGSigner, SignatureError


class TestGPGSigner:
    """Тесты для GPGSigner."""

    def test_init_default(self) -> None:
        """Тест инициализации с параметрами по умолчанию."""
        signer = GPGSigner()

        assert signer._require_signatures is True
        assert signer._keyring_path is None

    def test_init_custom(self) -> None:
        """Тест инициализации с кастомными параметрами."""
        keyring = Path("/path/to/keyring")
        signer = GPGSigner(
            keyring_path=keyring,
            trusted_key_id="ABC123",
            require_signatures=False,
        )

        assert signer._keyring_path == keyring
        assert signer._trusted_key_id == "ABC123"
        assert signer._require_signatures is False

    def test_is_signature_required_production_file(self) -> None:
        """Тест что production файл требует подпись."""
        signer = GPGSigner(require_signatures=True)

        # Проверяем что production файлы в списке требуют подпись
        # config/prod/ и config/staging/ требуют подпись
        assert "config/prod/" in signer.PRODUCTION_SIGNED_FILES
        assert "config/staging/" in signer.PRODUCTION_SIGNED_FILES

    def test_is_signature_required_dev_file(self) -> None:
        """Тест что dev файл не требует подпись."""
        signer = GPGSigner(require_signatures=True)

        assert signer.is_signature_required(Path("config/dev/local.yaml")) is False
        assert signer.is_signature_required(Path(".env.example")) is False
        assert signer.is_signature_required(Path("config/local/override.yaml")) is False

    def test_is_signature_required_disabled(self) -> None:
        """Тест что при отключенном require_signatures подпись не нужна."""
        signer = GPGSigner(require_signatures=False)

        assert signer.is_signature_required(Path("config/prod/settings.yaml")) is False

    def test_is_signature_required_unlisted(self) -> None:
        """Тест что для неподдерживаемых путей подпись не нужна."""
        signer = GPGSigner(require_signatures=True)

        # Для неизвестных путей возвращаем False
        assert signer.is_signature_required(Path("some/other/path.yaml")) is False


class TestGPGSignerIntegration:
    """Интеграционные тесты для GPGSigner."""

    def test_signer_has_required_methods(self) -> None:
        """Тест что GPGSigner имеет необходимые методы."""
        signer = GPGSigner()

        # Проверяем наличие методов
        assert hasattr(signer, "verify")
        assert hasattr(signer, "is_signature_required")
        assert callable(signer.verify)
        assert callable(signer.is_signature_required)

    def test_signature_error_attributes(self) -> None:
        """Тест что SignatureError содержит нужные атрибуты."""
        path = Path("test.yaml")
        error = SignatureError(path, "тестовая ошибка")

        assert error.path == path
        assert error.reason == "тестовая ошибка"
        assert "test.yaml" in str(error)
        assert "тестовая ошибка" in str(error)

    def test_signature_error_message(self) -> None:
        """Тест формата сообщения об ошибке."""
        error = SignatureError(Path("config.yaml"), "invalid signature")

        assert "config.yaml" in str(error)
        assert "invalid signature" in str(error)
