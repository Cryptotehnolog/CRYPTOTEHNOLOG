"""
GPG верификация подписей конфигурационных файлов.

Реализует интерфейс IConfigSigner для проверки GPG подписей.

Все docstrings на русском языке.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import subprocess

from cryptotechnolog.config.protocols import IConfigSigner, ISubprocessRunner


class SignatureError(Exception):
    """
    Ошибка проверки подписи.

    Атрибуты:
        path: Путь к файлу с ошибкой
        reason: Причина ошибки
    """

    def __init__(self, path: Path, reason: str) -> None:
        """
        Инициализировать ошибку подписи.

        Аргументы:
            path: Путь к файлу
            reason: Причина ошибки
        """
        self.path = path
        self.reason = reason
        message = f"Ошибка проверки подписи для {path}: {reason}"
        super().__init__(message)


class SubprocessRunner(ISubprocessRunner):
    """
    Реализация ISubprocessRunner через asyncio.
    """

    async def run(
        self,
        command: list[str],
        stdin: bytes | None = None,
    ) -> tuple[int, bytes, bytes]:
        """
        Выполнить команду.

        Аргументы:
            command: Команда и аргументы
            stdin: Данные для stdin

        Returns:
            Кортеж (return_code, stdout, stderr)
        """
        result = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE if stdin else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await result.communicate(input=stdin)
        return result.returncode, stdout, stderr  # type: ignore[return-value]


class GPGSigner(IConfigSigner):
    """
    Проверка GPG подписей конфигурационных файлов.

    Использует gpg для верификации подписей.
    В режиме development может быть отключено.

    Пример использования:
        signer = GPGSigner(keyring_path=Path("/path/to/keyring"))
        is_valid = await signer.verify(Path("config.yaml"))
    """

    # Файлы, которые требуют подписи в production
    PRODUCTION_SIGNED_FILES: frozenset[str] = frozenset(
        {
            "config/prod/",
            "config/staging/",
        }
    )

    # Файлы, которые не требуют подписи
    UNSIGNED_FILES: frozenset[str] = frozenset(
        {
            ".env.example",
            "config/dev/",
            "config/local/",
        }
    )

    def __init__(
        self,
        keyring_path: Path | None = None,
        trusted_key_id: str | None = None,
        require_signatures: bool = True,
        subprocess_runner: ISubprocessRunner | None = None,
    ) -> None:
        """
        Инициализировать GPG верификатор.

        Аргументы:
            keyring_path: Путь к директории с ключами
            trusted_key_id: ID доверенного ключа
            require_signatures: Требовать подписи в production
            subprocess_runner: Раннер для subprocess (для DI/тестирования)
        """
        self._keyring_path = keyring_path
        self._trusted_key_id = trusted_key_id
        self._require_signatures = require_signatures
        self._subprocess_runner = subprocess_runner or SubprocessRunner()
        self._gpg_available: bool | None = None

    async def verify(self, path: Path) -> bool:
        """
        Проверить подпись файла.

        Аргументы:
            path: Путь к файлу конфигурации

        Returns:
            True если подпись действительна

        Raises:
            SignatureError: При ошибке проверки подписи
        """
        # Проверяем, нужна ли подпись для этого файла
        if not self.is_signature_required(path):
            return True

        # Проверяем доступность gpg
        if not await self._check_gpg_available():
            raise SignatureError(path, "GPG недоступен")

        # Проверяем существование файла
        if not path.exists():
            raise SignatureError(path, "Файл не существует")

        # Проверяем существование файла подписи
        sig_path = Path(str(path) + ".sig")
        if not sig_path.exists():
            raise SignatureError(path, "Файл подписи не найден")

        # Выполняем верификацию
        try:
            result = await self._run_gpg_verify(path, sig_path)
            return result
        except Exception as e:
            raise SignatureError(path, str(e)) from e

    def is_signature_required(self, path: Path) -> bool:
        """
        Проверить, нужна ли подпись для файла.

        Аргументы:
            path: Путь к файлу конфигурации

        Returns:
            True если подпись требуется
        """
        if not self._require_signatures:
            return False

        path_str = str(path)

        # Проверяем файлы без подписи
        for unsigned in self.UNSIGNED_FILES:
            if unsigned.endswith("/"):
                if path_str.startswith(unsigned):
                    return False
            elif unsigned in path_str:
                return False

        # Проверяем production/staging файлы
        return any(path_str.startswith(signed) for signed in self.PRODUCTION_SIGNED_FILES)

    async def _check_gpg_available(self) -> bool:
        """
        Проверить доступность gpg.

        Returns:
            True если gpg доступен
        """
        if self._gpg_available is not None:
            return self._gpg_available

        try:
            returncode, _stdout, _stderr = await self._subprocess_runner.run(["gpg", "--version"])
            self._gpg_available = returncode == 0
        except FileNotFoundError:
            self._gpg_available = False

        return self._gpg_available

    async def _run_gpg_verify(self, path: Path, sig_path: Path) -> bool:
        """
        Выполнить команду gpg --verify.

        Аргументы:
            path: Путь к файлу
            sig_path: Путь к файлу подписи

        Returns:
            True если подпись действительна

        Raises:
            SignatureError: При ошибке верификации
        """
        cmd = ["gpg", "--verify", str(sig_path), str(path)]

        if self._keyring_path:
            cmd.extend(["--keyring", str(self._keyring_path)])

        if self._trusted_key_id:
            cmd.extend(["--trusted-key", self._trusted_key_id])

        try:
            returncode, _stdout, stderr = await self._subprocess_runner.run(cmd)

            if returncode == 0:
                return True

            # Анализируем вывод gpg
            error_output = stderr.decode("utf-8", errors="replace")
            if "Good signature" in error_output:
                return True
            if "BAD signature" in error_output:
                raise SignatureError(path, "Недействительная подпись")
            if "No signature" in error_output:
                raise SignatureError(path, "Подпись не найдена")

            raise SignatureError(path, f"GPG ошибка: {error_output[:200]}")

        except subprocess.CalledProcessError as e:
            raise SignatureError(path, f"Ошибка выполнения gpg: {e}") from e
