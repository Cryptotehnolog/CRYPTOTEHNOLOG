"""
Unit тесты для Config Providers.

Тестирование:
- FileConfigProvider: загрузка из файлов
- InfisicalConfigProvider: загрузка из Infisical
- EnvConfigProvider: загрузка из переменных окружения

Все docstrings на русском языке.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

from cryptotechnolog.config.providers import (
    EnvConfigProvider,
    FileConfigProvider,
    InfisicalConfigProvider,
)


class TestFileConfigProvider:
    """Тесты для FileConfigProvider."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Создать временную директорию."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def yaml_file(self, temp_dir: Path) -> Path:
        """Создать тестовый YAML файл."""
        file_path = temp_dir / "test.yaml"
        file_path.write_text("key: value\nnumber: 42\n", encoding="utf-8")
        return file_path

    @pytest.fixture
    def json_file(self, temp_dir: Path) -> Path:
        """Создать тестовый JSON файл."""
        file_path = temp_dir / "test.json"
        file_path.write_text('{"key": "value", "number": 42}', encoding="utf-8")
        return file_path

    @pytest.mark.asyncio
    async def test_load_yaml_file(self, yaml_file: Path) -> None:
        """Тест загрузки YAML файла."""
        provider = FileConfigProvider()
        result = await provider.load(str(yaml_file))

        assert b"key" in result
        assert b"value" in result
        assert b"number" in result

    @pytest.mark.asyncio
    async def test_load_json_file(self, json_file: Path) -> None:
        """Тест загрузки JSON файла."""
        provider = FileConfigProvider()
        result = await provider.load(str(json_file))

        data = json.loads(result)
        assert data["key"] == "value"
        assert data["number"] == 42

    @pytest.mark.asyncio
    async def test_load_file_not_found(self) -> None:
        """Тест ошибки при отсутствии файла."""
        provider = FileConfigProvider()

        with pytest.raises(FileNotFoundError):
            await provider.load("nonexistent.yaml")

    @pytest.mark.asyncio
    async def test_load_relative_path(self, temp_dir: Path) -> None:
        """Тест относительного пути."""
        test_file = temp_dir / "relative.yaml"
        test_file.write_text("test: data", encoding="utf-8")

        provider = FileConfigProvider(base_path=temp_dir)
        result = await provider.load("relative.yaml")

        assert b"test" in result

    @pytest.mark.asyncio
    async def test_reload(self, yaml_file: Path) -> None:
        """Тест перезагрузки."""
        provider = FileConfigProvider()
        await provider.load(str(yaml_file))

        result = await provider.reload()
        assert b"key" in result


class TestInfisicalConfigProvider:
    """Тесты для InfisicalConfigProvider."""

    def test_missing_token(self) -> None:
        """Тест ошибки при отсутствии INFISICAL_TOKEN."""
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(ValueError, match="INFISICAL_TOKEN"),
        ):
            InfisicalConfigProvider()

    @pytest.mark.asyncio
    async def test_load_secrets(self) -> None:
        """Тест загрузки секретов."""
        with patch.dict(
            os.environ,
            {"INFISICAL_TOKEN": "test_token", "INFISICAL_PROJECT_ID": "test_project"},
        ):
            provider = InfisicalConfigProvider()

            # Note: В реальном тесте нужно мокать HTTP клиент
            # Здесь просто проверяем что провайдер создаётся
            assert provider._token == "test_token"
            assert provider._project_id == "test_project"


class TestEnvConfigProvider:
    """Тесты для EnvConfigProvider."""

    def test_default_prefix(self) -> None:
        """Тест префикса по умолчанию."""
        provider = EnvConfigProvider()
        assert provider._prefix == "CT_"

    def test_custom_prefix(self) -> None:
        """Тест кастомного префикса."""
        provider = EnvConfigProvider(prefix="MYAPP_")
        assert provider._prefix == "MYAPP_"

    @pytest.mark.asyncio
    async def test_load_empty_env(self) -> None:
        """Тест пустого окружения."""
        with patch.dict(os.environ, {}, clear=True):
            provider = EnvConfigProvider()
            result = await provider.load("")

            data = json.loads(result)
            assert data == {}

    @pytest.mark.asyncio
    async def test_load_with_prefix(self) -> None:
        """Тест загрузки с префиксом."""
        env = {
            "CT_KEY": "value",
            "CT_NUMBER": "42",
            "OTHER_VAR": "ignored",
        }

        with patch.dict(os.environ, env, clear=True):
            provider = EnvConfigProvider(prefix="CT_")
            result = await provider.load("")

            data = json.loads(result)
            assert data["KEY"] == "value"
            assert data["NUMBER"] == 42
            assert "OTHER_VAR" not in data

    @pytest.mark.asyncio
    async def test_parse_boolean_true(self) -> None:
        """Тест парсинга boolean true."""
        with patch.dict(os.environ, {"CT_FLAG": "true"}, clear=True):
            provider = EnvConfigProvider()
            result = await provider.load("")

            data = json.loads(result)
            assert data["FLAG"] is True

    @pytest.mark.asyncio
    async def test_parse_boolean_false(self) -> None:
        """Тест парсинга boolean false."""
        with patch.dict(os.environ, {"CT_FLAG": "false"}, clear=True):
            provider = EnvConfigProvider()
            result = await provider.load("")

            data = json.loads(result)
            assert data["FLAG"] is False

    @pytest.mark.asyncio
    async def test_parse_integer(self) -> None:
        """Тест парсинга integer."""
        with patch.dict(os.environ, {"CT_COUNT": "123"}, clear=True):
            provider = EnvConfigProvider()
            result = await provider.load("")

            data = json.loads(result)
            assert data["COUNT"] == 123

    @pytest.mark.asyncio
    async def test_parse_float(self) -> None:
        """Тест парсинга float."""
        with patch.dict(os.environ, {"CT_PRICE": "123.45"}, clear=True):
            provider = EnvConfigProvider()
            result = await provider.load("")

            data = json.loads(result)
            assert data["PRICE"] == 123.45

    @pytest.mark.asyncio
    async def test_parse_json_object(self) -> None:
        """Тест парсинга JSON объекта."""
        with patch.dict(
            os.environ, {"CT_CONFIG": '{"key": "value", "nested": {"a": 1}}'}, clear=True
        ):
            provider = EnvConfigProvider()
            result = await provider.load("")

            data = json.loads(result)
            assert data["CONFIG"] == {"key": "value", "nested": {"a": 1}}

    @pytest.mark.asyncio
    async def test_reload_returns_cached(self) -> None:
        """Тест что reload возвращает кешированное значение."""
        with patch.dict(os.environ, {"CT_KEY": "value"}, clear=True):
            provider = EnvConfigProvider()
            await provider.load("")

            # Изменим env
            with patch.dict(os.environ, {"CT_KEY": "new_value"}, clear=True):
                result = await provider.reload()
                data = json.loads(result)
                assert data["KEY"] == "value"  # Старое значение


class TestEnvConfigProviderEdgeCases:
    """Edge cases для EnvConfigProvider."""

    @pytest.mark.asyncio
    async def test_empty_string_value(self) -> None:
        """Тест пустой строки."""
        with patch.dict(os.environ, {"CT_EMPTY": ""}, clear=True):
            provider = EnvConfigProvider()
            result = await provider.load("")

            data = json.loads(result)
            assert data["EMPTY"] == ""

    @pytest.mark.asyncio
    async def test_special_characters(self) -> None:
        """Тест спецсимволов."""
        with patch.dict(os.environ, {"CT_SPECIAL": "value with spaces!"}, clear=True):
            provider = EnvConfigProvider()
            result = await provider.load("")

            data = json.loads(result)
            assert data["SPECIAL"] == "value with spaces!"

    @pytest.mark.asyncio
    async def test_case_sensitivity(self) -> None:
        """Тест регистронезависимости."""
        with patch.dict(os.environ, {"ct_key": "lowercase", "CT_KEY": "uppercase"}, clear=True):
            provider = EnvConfigProvider(prefix="CT_")
            result = await provider.load("")

            data = json.loads(result)
            # Только CT_KEY (верхний регистр) должен быть
            assert data["KEY"] == "uppercase"
