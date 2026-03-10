"""
Тесты для парсеров конфигурации.

Тестирование:
    - YamlParser: парсинг YAML в словарь
    - JsonParser: парсинг JSON в словарь

Все docstrings на русском языке.
"""

import pytest

from cryptotechnolog.config.parsers import JsonParser, YamlParser
from cryptotechnolog.config.parsers.json_parser import JsonParseError
from cryptotechnolog.config.parsers.yaml_parser import YamlParseError


class TestYamlParser:
    """Тесты для YamlParser."""

    def test_parse_simple_yaml(self) -> None:
        """Тест парсинга простого YAML."""
        parser = YamlParser()
        data = b"version: '1.0.0'\nenvironment: production"

        result = parser.parse(data)

        assert result["version"] == "1.0.0"
        assert result["environment"] == "production"

    def test_parse_nested_yaml(self) -> None:
        """Тест парсинга вложенного YAML."""
        parser = YamlParser()
        data = b"""
risk:
  base_r_percent: 0.01
  max_drawdown_hard: 0.2
exchanges:
  - name: bybit
    enabled: true
"""

        result = parser.parse(data)

        assert result["risk"]["base_r_percent"] == 0.01
        assert result["risk"]["max_drawdown_hard"] == 0.2
        assert len(result["exchanges"]) == 1
        assert result["exchanges"][0]["name"] == "bybit"

    def test_parse_empty_data_raises_error(self) -> None:
        """Тест что пустые данные вызывают ошибку."""
        parser = YamlParser()

        with pytest.raises(YamlParseError) as exc_info:
            parser.parse(b"")

        assert "Пустые данные" in str(exc_info.value)

    def test_parse_invalid_yaml_raises_error(self) -> None:
        """Тест что невалидный YAML вызывает ошибку."""
        parser = YamlParser()
        data = b"version: 'unclosed string"

        with pytest.raises(YamlParseError) as exc_info:
            parser.parse(data)

        assert "Ошибка парсинга YAML" in str(exc_info.value)

    def test_parse_not_dict_raises_error(self) -> None:
        """Тест что парсинг не словаря вызывает ошибку."""
        parser = YamlParser()
        data = b"- item1\n- item2"

        with pytest.raises(YamlParseError) as exc_info:
            parser.parse(data)

        assert "Ожидался словарь" in str(exc_info.value)

    def test_parse_with_utf8_bom(self) -> None:
        """Тест парсинга UTF-8 с BOM."""
        parser = YamlParser()
        data = "\ufeffversion: '1.0.0'\nname: тест".encode()

        result = parser.parse(data)

        assert result["version"] == "1.0.0"

    def test_parse_with_comments(self) -> None:
        """Тест парсинга YAML с комментариями."""
        parser = YamlParser()
        data = """
# Комментарий
version: '1.0.0'  # inline комментарий
# Ещё комментарий
""".encode()

        result = parser.parse(data)

        assert result["version"] == "1.0.0"

    def test_parse_special_values(self) -> None:
        """Тест парсинга специальных значений YAML."""
        parser = YamlParser()
        data = b"""
null_value: null
bool_true: true
bool_false: false
int_value: 42
float_value: 3.14
string_value: hello
"""

        result = parser.parse(data)

        assert result["null_value"] is None
        assert result["bool_true"] is True
        assert result["bool_false"] is False
        assert result["int_value"] == 42
        assert result["float_value"] == 3.14
        assert result["string_value"] == "hello"


class TestJsonParser:
    """Тесты для JsonParser."""

    def test_parse_simple_json(self) -> None:
        """Тест парсинга простого JSON."""
        parser = JsonParser()
        data = b'{"version": "1.0.0", "environment": "production"}'

        result = parser.parse(data)

        assert result["version"] == "1.0.0"
        assert result["environment"] == "production"

    def test_parse_nested_json(self) -> None:
        """Тест парсинга вложенного JSON."""
        parser = JsonParser()
        data = b'{"risk": {"base_r_percent": 0.01}, "exchanges": [{"name": "bybit"}]}'

        result = parser.parse(data)

        assert result["risk"]["base_r_percent"] == 0.01
        assert len(result["exchanges"]) == 1

    def test_parse_empty_data_raises_error(self) -> None:
        """Тест что пустые данные вызывают ошибку."""
        parser = JsonParser()

        with pytest.raises(JsonParseError) as exc_info:
            parser.parse(b"")

        assert "Пустые данные" in str(exc_info.value)

    def test_parse_invalid_json_raises_error(self) -> None:
        """Тест что невалидный JSON вызывает ошибку."""
        parser = JsonParser()
        data = b'{"version": "unclosed"'

        with pytest.raises(JsonParseError) as exc_info:
            parser.parse(data)

        assert "Ошибка парсинга JSON" in str(exc_info.value)

    def test_parse_not_dict_raises_error(self) -> None:
        """Тест что парсинг не словаря вызывает ошибку."""
        parser = JsonParser()
        data = b'["item1", "item2"]'

        with pytest.raises(JsonParseError) as exc_info:
            parser.parse(data)

        assert "Ожидался словарь" in str(exc_info.value)

    def test_parse_with_special_values(self) -> None:
        """Тест парсинга специальных значений JSON."""
        parser = JsonParser()
        data = b'{"null": null, "bool_true": true, "bool_false": false, "num": 42}'

        result = parser.parse(data)

        assert result["null"] is None
        assert result["bool_true"] is True
        assert result["bool_false"] is False
        assert result["num"] == 42

    def test_parse_unicode(self) -> None:
        """Тест парсинга Unicode символов."""
        parser = JsonParser()
        data = '{"name": "Тест Unicode 日本語"}'.encode()

        result = parser.parse(data)

        assert result["name"] == "Тест Unicode 日本語"

    def test_parse_whitespace(self) -> None:
        """Тест парсинга JSON с пробелами."""
        parser = JsonParser()
        data = b'  {  "version"  :  "1.0.0"  }  '

        result = parser.parse(data)

        assert result["version"] == "1.0.0"


class TestParserIntegration:
    """Интеграционные тесты для парсеров."""

    def test_yaml_to_json_via_parsers(self) -> None:
        """Тест преобразования YAML -> JSON через парсеры."""
        yaml_parser = YamlParser()

        yaml_data = b"""
{
    "version": "1.0.0",
    "risk": {
        "base_r_percent": 0.01
    }
}
"""
        # Парсим как YAML (хотя это JSON, но SafeLoader может это прочитать)
        result = yaml_parser.parse(yaml_data)

        assert result["version"] == "1.0.0"
        assert result["risk"]["base_r_percent"] == 0.01

    def test_both_parsers_implement_protocol(self) -> None:
        """Тест что оба парсера реализуют IConfigParser."""
        yaml_parser = YamlParser()
        json_parser = JsonParser()

        # Проверяем наличие метода parse (structural typing)
        assert hasattr(yaml_parser, "parse")
        assert hasattr(json_parser, "parse")
        assert callable(yaml_parser.parse)
        assert callable(json_parser.parse)
