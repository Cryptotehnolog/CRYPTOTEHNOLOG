"""
Mock Logger — Заглушка логгера для тестирования.

Записывает все вызовы в список для проверки в тестах.
"""

from typing import Any


class MockLogger:
    """
    Mock реализация Logger для тестирования.

    Записывает все сообщения в список для проверки в тестах.
    """

    def __init__(self) -> None:
        """Инициализировать mock логгер."""
        self.messages: list[dict[str, Any]] = []

    def _log(self, level: str, msg: str, *args: Any, **kwargs: Any) -> None:
        """Записать сообщение в список."""
        self.messages.append(
            {
                "level": level,
                "message": msg,
                "args": args,
                "kwargs": kwargs,
            }
        )

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log("DEBUG", msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log("INFO", msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log("WARNING", msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log("ERROR", msg, *args, **kwargs)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log("CRITICAL", msg, *args, **kwargs)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log("EXCEPTION", msg, *args, **kwargs)

    def bind(self, **kwargs: Any) -> "MockLogger":
        """Вернуть новый MockLogger с привязанным контекстом."""
        new_logger = MockLogger()
        new_logger.messages = self.messages  # Share messages
        return new_logger

    def clear(self) -> None:
        """Очистить все сообщения."""
        self.messages.clear()

    # ==================== Утилиты для тестов ====================

    def get_messages_by_level(self, level: str) -> list[dict[str, Any]]:
        """Получить сообщения определённого уровня."""
        return [m for m in self.messages if m["level"] == level]

    def get_messages_containing(self, text: str) -> list[dict[str, Any]]:
        """Получить сообщения содержащие текст."""
        return [m for m in self.messages if text in m["message"]]

    def assert_logged(self, level: str, message: str) -> None:
        """Проверить что сообщение было залогировано."""
        for msg in self.messages:
            if msg["level"] == level and msg["message"] == message:
                return
        raise AssertionError(f"Expected log: [{level}] {message}")

    def assert_not_logged(self, level: str, message: str) -> None:
        """Проверить что сообщение НЕ было залогировано."""
        for msg in self.messages:
            if msg["level"] == level and msg["message"] == message:
                raise AssertionError(f"Unexpected log: [{level}] {message}")
