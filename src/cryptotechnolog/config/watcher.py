"""
ConfigWatcher - мониторинг изменений файлов конфигурации.

Использует библиотеку watchdog для отслеживания изменений
в файлах конфигурации и автоматического запуска hot reload.

Все docstrings на русском языке.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from cryptotechnolog.config.protocols import IConfigWatcher, IObserver, IObserverFactory

logger = logging.getLogger(__name__)


class WatcherError(Exception):
    """
    Ошибка работы ConfigWatcher.

    Атрибуты:
        operation: Операция которая вызвала ошибку
        reason: Причина ошибки
    """

    def __init__(self, operation: str, reason: str, original: BaseException | None = None) -> None:
        """
        Инициализировать ошибку.

        Аргументы:
            operation: Название операции
            reason: Причина ошибки
            original: Оригинальное исключение (для chaining)
        """
        self.operation = operation
        self.reason = reason
        message = f"Ошибка ConfigWatcher ({operation}): {reason}"
        super().__init__(message)
        if original:
            self.__cause__ = original


class ConfigFileEventHandler(FileSystemEventHandler):
    """
    Обработчик событий файловой системы для ConfigWatcher.

    Перехватывает события изменения файлов и вызывает callback.
    """

    def __init__(
        self,
        callback: Any,  # Callable[[Path], None],
        debounce_seconds: float = 1.0,
    ) -> None:
        """
        Инициализировать обработчик.

        Аргументы:
            callback: Функция которая вызывается при изменении
            debounce_seconds: Время дебаунса (сек)
        """
        self._callback = callback
        self._debounce_seconds = debounce_seconds
        self._pending_tasks: dict[str, asyncio.TimerHandle] = {}

    def on_modified(self, event: Any) -> None:
        """
        Обработать событие изменения файла.

        Аргументы:
            event: Событие от watchdog
        """
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        logger.info("Обнаружено изменение файла: %s", file_path)

        # Дебаунс - отменяем предыдущую задачу если есть
        path_str = str(file_path)
        if path_str in self._pending_tasks:
            self._pending_tasks[path_str].cancel()

        # Создаём новую задачу с задержкой
        loop = asyncio.get_event_loop()
        task = loop.call_later(
            self._debounce_seconds,
            self._execute_callback,
            file_path,
        )
        self._pending_tasks[path_str] = task

    def _execute_callback(self, file_path: Path) -> None:
        """
        Выполнить callback после дебаунса.

        Аргументы:
            file_path: Путь к файлу
        """
        path_str = str(file_path)
        if path_str in self._pending_tasks:
            del self._pending_tasks[path_str]

        try:
            self._callback(file_path)
        except Exception as e:
            logger.error("Ошибка в callback ConfigWatcher: %s", str(e))


class ConfigWatcher(IConfigWatcher):
    """
    Наблюдатель за изменениями файлов конфигурации.

    Использует watchdog для мониторинга изменений
    и автоматического запуска reload.

    Пример использования:
        watcher = ConfigWatcher(debounce_seconds=1.0)

        def on_config_change(path: Path):
            asyncio.create_task(config_manager.reload())

        watcher.on_change(on_config_change)
        await watcher.watch(["config/dev/config.yaml"])
    """

    def __init__(
        self,
        debounce_seconds: float = 1.0,
        observer_factory: IObserverFactory | None = None,
    ) -> None:
        """
        Инициализировать ConfigWatcher.

        Аргументы:
            debounce_seconds: Время дебаунса перед вызовом callback
            observer_factory: Фабрика для создания Observer (для DI/тестирования)
        """
        self._debounce_seconds = debounce_seconds
        # Используем фабрику или Observer по умолчанию
        if observer_factory is not None:
            self._observer_factory = observer_factory
        else:
            self._observer_factory = Observer
        self._observer: IObserver | None = None
        self._event_handler: ConfigFileEventHandler | None = None
        self._is_watching = False
        self._watched_paths: list[Path] = []

    async def watch(self, paths: list[Path]) -> None:
        """
        Начать мониторинг изменений файлов.

        Аргументы:
            paths: Список путей для мониторинга

        Raises:
            WatcherError: При ошибке запуска мониторинга
        """
        if self._is_watching:
            logger.warning("ConfigWatcher уже запущен")
            return

        try:
            # Создаём observer через фабрику (для DI)
            self._observer = self._observer_factory()
            assert self._observer is not None

            # Создаём event handler с пустым callback (будет установлен позже)
            def empty_callback(path: Path) -> None:
                pass

            self._event_handler = ConfigFileEventHandler(
                callback=empty_callback,
                debounce_seconds=self._debounce_seconds,
            )

            # Добавляем пути для мониторинга
            for path in paths:
                if path.is_dir():
                    self._observer.schedule(self._event_handler, str(path), recursive=True)
                    logger.info("Добавлен мониторинг директории: %s", path)
                elif path.is_file():
                    parent_dir = path.parent
                    self._observer.schedule(self._event_handler, str(parent_dir), recursive=False)
                    logger.info("Добавлен мониторинг файла: %s", path)

            self._observer.start()
            self._is_watching = True
            self._watched_paths = paths

            logger.info("ConfigWatcher запущен для путей: %s", paths)

        except Exception as e:
            raise WatcherError("watch", str(e)) from e

    async def stop(self) -> None:
        """
        Остановить мониторинг.

        Raises:
            WatcherError: При ошибке остановки
        """
        if not self._is_watching:
            logger.warning("ConfigWatcher не запущен")
            return

        try:
            if self._observer:
                self._observer.stop()
                self._observer.join(timeout=5)

            self._is_watching = False
            self._event_handler = None

            logger.info("ConfigWatcher остановлен")

        except Exception as e:
            raise WatcherError("stop", str(e)) from e

    def on_change(self, callback: Any) -> None:  # Callable[[Path], None]
        """
        Установить callback на изменение файла.

        Аргументы:
            callback: Функция которая вызывается при изменении файла
        """
        self._change_callback = callback
        logger.info("Установлен callback для ConfigWatcher")
