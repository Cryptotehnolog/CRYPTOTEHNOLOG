"""
Unit тесты для ConfigWatcher.

Тестирование мониторинга изменений файлов конфигурации.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cryptotechnolog.config.watcher import ConfigFileEventHandler, ConfigWatcher, WatcherError


class TestConfigWatcherInit:
    """Тесты инициализации ConfigWatcher."""

    def test_init_success(self) -> None:
        """Тест успешной инициализации."""
        watcher = ConfigWatcher(debounce_seconds=2.0)

        assert watcher._debounce_seconds == 2.0
        assert watcher._observer is None
        assert watcher._event_handler is None
        assert watcher._is_watching is False
        assert watcher._watched_paths == []

    def test_init_with_custom_factory(self) -> None:
        """Тест инициализации с кастомной фабрикой observer."""
        mock_factory = MagicMock()

        watcher = ConfigWatcher(observer_factory=mock_factory)

        assert watcher._observer_factory is mock_factory

    def test_current_config_property(self) -> None:
        """Тест свойства is_watching."""
        watcher = ConfigWatcher()

        # Проверяем что _is_watching по умолчанию False
        assert watcher._is_watching is False


class TestConfigWatcherWatch:
    """Тесты метода watch."""

    @pytest.mark.asyncio
    async def test_watch_success(self) -> None:
        """Тест успешного запуска мониторинга."""
        watcher = ConfigWatcher()

        # Мокаем Observer
        mock_observer = MagicMock()
        watcher._observer_factory = MagicMock(return_value=mock_observer)

        # Создаём временную директорию для теста
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir) / "config"
            test_path.mkdir()

            # Мокаем event_handler чтобы не было ошибок
            with patch.object(ConfigWatcher, "_update_callback", create=True):
                await watcher.watch([test_path])

            assert watcher._is_watching is True
            assert watcher._watched_paths == [test_path]
            mock_observer.schedule.assert_called()
            mock_observer.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_watch_already_watching(self) -> None:
        """Тест повторного запуска мониторинга."""
        watcher = ConfigWatcher()
        watcher._is_watching = True

        # Не должен вызывать ошибку, а просто вернуть
        await watcher.watch([Path("config/dev")])

    @pytest.mark.asyncio
    async def test_watch_invalid_path(self) -> None:
        """Тест запуска мониторинга с несуществующим путём."""
        watcher = ConfigWatcher()

        mock_observer = MagicMock()
        watcher._observer_factory = MagicMock(return_value=mock_observer)

        with patch.object(ConfigWatcher, "_update_callback", create=True):
            # Path.is_dir() и Path.is_file() вернут False для несуществующего пути
            await watcher.watch([Path("nonexistent")])


class TestConfigWatcherStop:
    """Тесты метода stop."""

    @pytest.mark.asyncio
    async def test_stop_success(self) -> None:
        """Тест успешной остановки мониторинга."""
        watcher = ConfigWatcher()

        # Устанавливаем состояние "запущен"
        mock_observer = MagicMock()
        watcher._observer = mock_observer
        watcher._is_watching = True
        watcher._event_handler = MagicMock()

        await watcher.stop()

        assert watcher._is_watching is False
        assert watcher._event_handler is None
        mock_observer.stop.assert_called_once()
        mock_observer.join.assert_called_once_with(timeout=5)

    @pytest.mark.asyncio
    async def test_stop_not_watching(self) -> None:
        """Тест остановки когда не запущен."""
        watcher = ConfigWatcher()

        # Не должен вызывать ошибку
        await watcher.stop()


class TestConfigWatcherOnChange:
    """Тесты метода on_change."""

    def test_on_change(self) -> None:
        """Тест установки callback."""
        watcher = ConfigWatcher()

        callback = MagicMock()
        watcher.on_change(callback)

        # Callback должен быть установлен
        assert hasattr(watcher, "_change_callback")


class TestConfigFileEventHandler:
    """Тесты ConfigFileEventHandler."""

    def test_init(self) -> None:
        """Тест инициализации."""
        callback = MagicMock()
        handler = ConfigFileEventHandler(callback=callback, debounce_seconds=1.5)

        assert handler._callback is callback
        assert handler._debounce_seconds == 1.5

    def test_on_modified_directory(self) -> None:
        """Тест игнорирования директорий."""
        callback = MagicMock()
        handler = ConfigFileEventHandler(callback=callback)

        mock_event = MagicMock()
        mock_event.is_directory = True
        mock_event.src_path = "/path/to/dir"

        handler.on_modified(mock_event)

        # Callback не должен вызываться для директорий
        callback.assert_not_called()

    def test_on_modified_file(self) -> None:
        """Тест обработки изменения файла."""
        callback = MagicMock()
        handler = ConfigFileEventHandler(callback=callback, debounce_seconds=0.1)

        mock_event = MagicMock()
        mock_event.is_directory = False
        mock_event.src_path = "/path/to/config.yaml"

        # Запускаем в event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            handler.on_modified(mock_event)

            # Ждём выполнения callback после дебаунса
            loop.run_until_complete(asyncio.sleep(0.2))

            callback.assert_called_once()
        finally:
            loop.close()


class TestWatcherError:
    """Тесты исключения WatcherError."""

    def test_error_creation(self) -> None:
        """Тест создания ошибки."""
        error = WatcherError("watch", "test reason")

        assert error.operation == "watch"
        assert error.reason == "test reason"
        assert "Ошибка ConfigWatcher" in str(error)
        assert "watch" in str(error)
        assert "test reason" in str(error)

    def test_error_with_original(self) -> None:
        """Тест ошибки с оригинальным исключением."""
        original = ValueError("original")
        error = WatcherError("watch", "test", original=original)

        assert error.__cause__ is original
