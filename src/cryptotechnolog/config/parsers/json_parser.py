"""
Парсер JSON конфигурации.

Реализует интерфейс IConfigParser для парсинга JSON файлов.

Все docstrings на русском языке.
"""

import json
from typing import Any

from cryptotechnolog.config.protocols import IConfigParser


class JsonParseError(Exception):
    """Ошибка парсинга JSON."""

    pass


class JsonParser(IConfigParser):
    """
    Парсер JSON конфигурации.

    Преобразует байты JSON в словарь Python.
    Использует стандартный json модуль.

    Пример использования:
        parser = JsonParser()
        data = parser.parse(b'{"version": "1.0.0", "environment": "prod"}')
    """

    def __init__(self) -> None:
        """
        Инициализировать парсер JSON.

        Парсер настроен для безопасной обработки JSON с гибкими параметрами.
        """
        pass

    def parse(self, data: bytes) -> dict[str, Any]:
        """
        Распарсить JSON данные в словарь.

        Аргументы:
            data: Байты JSON конфигурации

        Returns:
            Словарь с конфигурацией

        Raises:
            JsonParseError: При ошибке парсинга JSON
        """
        if not data:
            raise JsonParseError("Пустые данные для парсинга JSON")

        try:
            # Декодируем байты в строку
            text = data.decode("utf-8")

            # Парсим JSON
            result = json.loads(text)

            # Проверяем, что результат словарь
            if result is None:
                raise JsonParseError("JSON документ пуст")
            if not isinstance(result, dict):
                raise JsonParseError(f"Ожидался словарь, получен {type(result).__name__}")

            return result

        except json.JSONDecodeError as e:
            raise JsonParseError(
                f"Ошибка парсинга JSON: {e.msg} (строка {e.lineno}, столбец {e.colno})"
            ) from e
        except UnicodeDecodeError as e:
            raise JsonParseError(f"Ошибка декодирования UTF-8: {e}") from e
