"""
Тесты для GPGSigner.

Тестирование:
    - GPGSigner: верификация GPG подписей

Все docstrings на русском языке.
"""

from pathlib import Path
import subprocess
from unittest.mock import AsyncMock, MagicMock

import pytest

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


class TestGPGSignerVerify:
    """Тесты метода verify."""

    @pytest.mark.asyncio
    async def test_verify_no_signature_required(self) -> None:
        """Тест verify когда подпись не требуется."""
        signer = GPGSigner(require_signatures=False)
        result = await signer.verify(Path("config/prod/settings.yaml"))

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_success(self, tmp_path: Path) -> None:
        """Тест успешной верификации."""
        # Создаём файл конфигурации в production папке
        prod_dir = tmp_path / "prod"
        prod_dir.mkdir()
        config_file = prod_dir / "settings.yaml"
        sig_file = prod_dir / "settings.yaml.sig"
        config_file.write_text("version: 1.0.0")
        sig_file.write_text("signature data")

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(return_value=(0, b"", b"Good signature"))
        signer = GPGSigner(
            require_signatures=True,
            subprocess_runner=mock_runner,
        )
        signer._gpg_available = True

        result = await signer.verify(config_file)

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_signature_error(self, tmp_path: Path) -> None:
        """Тест verify с SignatureError."""
        # Создаём файл конфигурации в production папке
        prod_dir = tmp_path / "prod"
        prod_dir.mkdir()
        config_file = prod_dir / "settings.yaml"
        sig_file = prod_dir / "settings.yaml.sig"
        config_file.write_text("version: 1.0.0")
        sig_file.write_text("signature data")

        # Мок возвращает ошибку GPG
        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(return_value=(2, b"", b"Some gpg error"))
        signer = GPGSigner(
            require_signatures=True,
            subprocess_runner=mock_runner,
        )
        signer._gpg_available = True

        # Должно выбросить SignatureError
        try:
            await signer.verify(config_file)
        except SignatureError as e:
            assert "GPG ошибка" in str(e)


class TestGPGSignerInternal:
    """Тесты внутренних методов GPGSigner."""

    @pytest.mark.asyncio
    async def test_check_gpg_available_cache(self) -> None:
        """Тест кэширования результата проверки GPG."""
        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(return_value=(0, b"gpg version 2.4.0", b""))
        signer = GPGSigner(subprocess_runner=mock_runner)

        # Первый вызов
        result1 = await signer._check_gpg_available()
        assert result1 is True

        # Второй вызов - должен использовать кэш
        mock_runner.run.assert_called_once()
        result2 = await signer._check_gpg_available()
        assert result2 is True

    @pytest.mark.asyncio
    async def test_check_gpg_not_available(self) -> None:
        """Тест когда GPG недоступен."""
        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(side_effect=FileNotFoundError("gpg not found"))
        signer = GPGSigner(subprocess_runner=mock_runner)

        result = await signer._check_gpg_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_check_gpg_error(self) -> None:
        """Тест когда GPG возвращает ошибку."""
        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(return_value=(1, b"", b"error"))
        signer = GPGSigner(subprocess_runner=mock_runner)

        result = await signer._check_gpg_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_run_gpg_verify_with_keyring(self, tmp_path: Path) -> None:
        """Тест верификации с указанием keyring."""
        config_file = tmp_path / "config.yaml"
        sig_file = tmp_path / "config.yaml.sig"
        keyring = tmp_path / "keyring"
        config_file.write_text("version: 1.0.0")
        sig_file.write_text("signature data")

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(return_value=(0, b"", b"Good signature"))
        signer = GPGSigner(
            keyring_path=keyring,
            subprocess_runner=mock_runner,
        )

        result = await signer._run_gpg_verify(config_file, sig_file)

        assert result is True
        # Проверяем что keyring передан в команду
        call_args = mock_runner.run.call_args
        cmd = call_args.args[0]
        assert "--keyring" in cmd

    @pytest.mark.asyncio
    async def test_run_gpg_verify_with_trusted_key(self, tmp_path: Path) -> None:
        """Тест верификации с указанием trusted_key."""
        config_file = tmp_path / "config.yaml"
        sig_file = tmp_path / "config.yaml.sig"
        config_file.write_text("version: 1.0.0")
        sig_file.write_text("signature data")

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(return_value=(0, b"", b"Good signature"))
        signer = GPGSigner(
            trusted_key_id="ABC123",
            subprocess_runner=mock_runner,
        )

        result = await signer._run_gpg_verify(config_file, sig_file)

        assert result is True
        # Проверяем что trusted_key передан в команду
        call_args = mock_runner.run.call_args
        cmd = call_args.args[0]
        assert "--trusted-key" in cmd
        assert "ABC123" in cmd

    @pytest.mark.asyncio
    async def test_run_gpg_verify_called_process_error(self, tmp_path: Path) -> None:
        """Тест верификации с CalledProcessError."""
        config_file = tmp_path / "config.yaml"
        sig_file = tmp_path / "config.yaml.sig"
        config_file.write_text("version: 1.0.0")
        sig_file.write_text("signature data")

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(side_effect=subprocess.CalledProcessError(1, "gpg"))
        signer = GPGSigner(subprocess_runner=mock_runner)

        with pytest.raises(SignatureError) as exc_info:
            await signer._run_gpg_verify(config_file, sig_file)

        assert "Ошибка выполнения gpg" in str(exc_info.value)


class TestSubprocessRunner:
    """Тесты SubprocessRunner - требуют мокинг."""

    @pytest.mark.asyncio
    async def test_subprocess_runner_mock(self) -> None:
        """Тест SubprocessRunner через мок."""
        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(return_value=(0, b"output", b""))

        result = await mock_runner.run(["echo", "hello"])

        assert result == (0, b"output", b"")


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
