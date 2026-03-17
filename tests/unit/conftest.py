# ==================== Unit Tests Configuration ====================
# Minimal conftest for unit tests - no database required

import asyncio
import os
import sys
from typing import TYPE_CHECKING

import pytest

from cryptotechnolog.config.settings import Settings

# Windows asyncio fix
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if TYPE_CHECKING:
    from collections.abc import Generator

# Set test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "true"


# ==================== Event Loop Fixture ====================


@pytest.fixture(scope="function")
def event_loop() -> "Generator[asyncio.AbstractEventLoop, None, None]":
    """Создать новый event loop для каждого теста.

    Это предотвращает ошибки 'Event loop is closed' между тестами.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    # Отменяем все ожидающие задачи
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()
    # Дожидаемся завершения отменённых задач
    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    loop.close()


# ==================== Settings Fixtures ====================


@pytest.fixture
def test_env(monkeypatch: pytest.MonkeyPatch) -> "Generator[dict[str, str], None, None]":
    """Set test environment."""
    env_vars = {
        "ENVIRONMENT": "test",
        "DEBUG": "true",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    yield env_vars


@pytest.fixture
def test_settings(test_env: dict[str, str]):
    """Return test settings instance."""
    return Settings()
