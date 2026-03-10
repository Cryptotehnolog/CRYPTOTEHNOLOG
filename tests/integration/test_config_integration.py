"""
Интеграционные тесты для ConfigWatcher.

Тестирование взаимодействия с файловой системой и event handling.
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cryptotechnolog.config.watcher import (
    ConfigFileEventHandler,
    ConfigWatcher,
    WatcherError,
)


class TestConfigWatcherFileSystemIntegration:
    """
    Интеграционные тесты ConfigWatcher с файловой системой.

    Проверяют реальное взаимодействие с файлами и директориями.
    """

    @pytest.mark.asyncio
    async def test_watch_directory_creates_observer(
        self,
        tmp_path: Path,
    ) -> None:
        """
        Тест: мониторинг директории создаёт observer.

        Проверяем что при вызове watch() создаётся и запускается observer.
        """
        test_dir = tmp_path / "config"
        test_dir.mkdir()

        # Мокаем Observer
        mock_observer = MagicMock()
        mock_observer.schedule = MagicMock()
        mock_observer.start = MagicMock()
        mock_observer.stop = MagicMock()
        mock_observer.join = MagicMock()

        watcher = ConfigWatcher(observer_factory=lambda: mock_observer)

        # Запускаем мониторинг
        await watcher.watch([test_dir])

        # Проверяем что observer был создан и запущен
        mock_observer.schedule.assert_called()
        mock_observer.start.assert_called_once()
        assert watcher._is_watching is True

        await watcher.stop()

    @pytest.mark.asyncio
    async def test_watch_file_creates_observer(
        self,
        tmp_path: Path,
    ) -> None:
        """
        Тест: мониторинг файла создаёт observer.

        Проверяем что при мониторинге файла observer настраивается на parent dir.
        """
        config_file = tmp_path / "config.yaml"
        config_file.write_text("test: value")

        mock_observer = MagicMock()
        mock_observer.schedule = MagicMock()
        mock_observer.start = MagicMock()
        mock_observer.stop = MagicMock()
        mock_observer.join = MagicMock()

        watcher = ConfigWatcher(observer_factory=lambda: mock_observer)

        await watcher.watch([config_file])

        # Observer должен быть настроен
        mock_observer.schedule.assert_called()
        mock_observer.start.assert_called_once()

        await watcher.stop()

    @pytest.mark.asyncio
    async def test_multiple_paths_watch(
        self,
        tmp_path: Path,
    ) -> None:
        """
        Тест: мониторинг нескольких путей.

        Проверяем что можно мониторить несколько директорий/файлов.
        """
        dir1 = tmp_path / "config1"
        dir2 = tmp_path / "config2"
        dir1.mkdir()
        dir2.mkdir()

        mock_observer_instance = MagicMock()
        mock_observer = MagicMock(return_value=mock_observer_instance)
        mock_observer_instance.schedule = MagicMock()
        mock_observer_instance.start = MagicMock()
        mock_observer_instance.stop = MagicMock()
        mock_observer_instance.join = MagicMock()

        watcher = ConfigWatcher(observer_factory=mock_observer)

        await watcher.watch([dir1, dir2])

        # Для каждой директории должен быть вызван schedule
        assert mock_observer_instance.schedule.call_count == 2

        await watcher.stop()

    @pytest.mark.asyncio
    async def test_watcher_error_handling(
        self,
        tmp_path: Path,
    ) -> None:
        """
        Тест: обработка ошибок при мониторинге.

        Проверяем что ошибки корректно обрабатываются.
        """
        # Мокаем Observer который выбрасывает исключение
        mock_observer = MagicMock()
        mock_observer.schedule.side_effect = OSError("Permission denied")
        mock_observer.start = MagicMock()

        watcher = ConfigWatcher(observer_factory=lambda: mock_observer)

        # Должна выбрасываться ошибка
        with pytest.raises(WatcherError):
            await watcher.watch([tmp_path])

    @pytest.mark.asyncio
    async def test_double_watch_prevented(
        self,
        tmp_path: Path,
    ) -> None:
        """
        Тест: повторный вызов watch не создаёт новый observer.

        Проверяем что второй вызов watch без stop игнорируется.
        """
        test_dir = tmp_path / "config"
        test_dir.mkdir()

        mock_observer = MagicMock()
        mock_observer.schedule = MagicMock()
        mock_observer.start = MagicMock()

        watcher = ConfigWatcher(observer_factory=lambda: mock_observer)

        # Первый вызов
        await watcher.watch([test_dir])
        first_call_count = mock_observer.start.call_count

        # Второй вызов без остановки
        await watcher.watch([test_dir])
        second_call_count = mock_observer.start.call_count

        # Observer не должен быть запущен дважды
        assert first_call_count == second_call_count

        await watcher.stop()


class TestConfigFileEventHandlerIntegration:
    """
    Интеграционные тесты обработчика событий файловой системы.
    """

    @pytest.mark.asyncio
    async def test_event_handler_debounce(
        self,
        tmp_path: Path,
    ) -> None:
        """
        Тест: дебаунс событий.

        Проверяем что несколько событий за короткое время
        приводят только к одному вызову callback.
        """
        callback = MagicMock()
        handler = ConfigFileEventHandler(
            callback=callback,
            debounce_seconds=0.2,
        )

        config_file = tmp_path / "config.yaml"
        config_file.write_text("test: value")

        # Симулируем несколько событий модификации
        for _ in range(3):
            event = MagicMock()
            event.is_directory = False
            event.src_path = str(config_file)
            handler.on_modified(event)

        # Ждём выполнения дебаунса
        await asyncio.sleep(0.3)

        # Callback должен быть вызван только один раз
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_event_handler_ignores_directories(
        self,
        tmp_path: Path,
    ) -> None:
        """
        Тест: игнорирование событий от директорий.

        Проверяем что события от директорий не вызывают callback.
        """
        callback = MagicMock()
        handler = ConfigFileEventHandler(callback=callback)

        event = MagicMock()
        event.is_directory = True
        event.src_path = str(tmp_path)

        handler.on_modified(event)

        # Callback не должен вызываться для директорий
        callback.assert_not_called()


class TestConfigWatcherStopIntegration:
    """
    Интеграционные тесты остановки watcher.
    """

    @pytest.mark.asyncio
    async def test_stop_observer(
        self,
        tmp_path: Path,
    ) -> None:
        """
        Тест: остановка observer.

        Проверяем что stop() корректно останавливает observer.
        """
        test_dir = tmp_path / "config"
        test_dir.mkdir()

        mock_observer = MagicMock()
        mock_observer.schedule = MagicMock()
        mock_observer.start = MagicMock()
        mock_observer.stop = MagicMock()
        mock_observer.join = MagicMock()

        watcher = ConfigWatcher(observer_factory=lambda: mock_observer)

        await watcher.watch([test_dir])
        await watcher.stop()

        # Observer должен быть остановлен
        mock_observer.stop.assert_called_once()
        mock_observer.join.assert_called_once_with(timeout=5)

    @pytest.mark.asyncio
    async def test_stop_when_not_watching(
        self,
        tmp_path: Path,
    ) -> None:
        """
        Тест: остановка когда watcher не запущен.

        Проверяем что вызов stop() когда watcher не активен не вызывает ошибку.
        """
        watcher = ConfigWatcher()

        # Не должно выбрасываться исключение
        await watcher.stop()

    @pytest.mark.asyncio
    async def test_watcher_state_after_stop(
        self,
        tmp_path: Path,
    ) -> None:
        """
        Тест: состояние watcher после остановки.

        Проверяем что состояние корректно обновляется после stop().
        """
        test_dir = tmp_path / "config"
        test_dir.mkdir()

        mock_observer = MagicMock()
        mock_observer.schedule = MagicMock()
        mock_observer.start = MagicMock()
        mock_observer.stop = MagicMock()
        mock_observer.join = MagicMock()

        watcher = ConfigWatcher(observer_factory=lambda: mock_observer)

        await watcher.watch([test_dir])
        assert watcher._is_watching is True

        await watcher.stop()
        assert watcher._is_watching is False
        assert watcher._event_handler is None
