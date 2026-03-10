"""
Парсер YAML конфигурации.

Реализует интерфейс IConfigParser для парсинга YAML файлов.

Все docstrings на русском языке.
"""

from typing import Any

import yaml

from cryptotechnolog.config.protocols import IConfigParser


class YamlParseError(Exception):
    """Ошибка парсинга YAML."""

    pass


class YamlParser(IConfigParser):
    """
    Парсер YAML конфигурации.

    Преобразует байты YAML в словарь Python.
    Использует безопасную загрузку без выполнения произвольного кода.

    Пример использования:
        parser = YamlParser()
        data = parser.parse(b"version: '1.0.0'\\nenvironment: prod")
    """

    def __init__(self) -> None:
        """
        Инициализировать парсер YAML.

        Использует SafeLoader для безопасной загрузки без выполнения кода.
        """
        self._loader = yaml.SafeLoader

    def parse(self, data: bytes) -> dict[str, Any]:
        """
        Распарсить YAML данные в словарь.

        Аргументы:
            data: Байты YAML конфигурации

        Returns:
            Словарь с конфигурацией

        Raises:
            YamlParseError: При ошибке парсинга YAML
        """
        if not data:
            raise YamlParseError("Пустые данные для парсинга YAML")

        try:
            # Декодируем байты в строку
            text = data.decode("utf-8")

            # Парсим YAML (используем SafeLoader для безопасности)
            result = yaml.load(text, Loader=self._loader)

            # Проверяем, что результат словарь
            if result is None:
                raise YamlParseError("YAML документ пуст")
            if not isinstance(result, dict):
                raise YamlParseError(f"Ожидался словарь, получен {type(result).__name__}")

            return result

        except yaml.YAMLError as e:
            raise YamlParseError(f"Ошибка парсинга YAML: {e}") from e
        except UnicodeDecodeError as e:
            raise YamlParseError(f"Ошибка декодирования UTF-8: {e}") from e
