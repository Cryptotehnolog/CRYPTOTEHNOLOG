from __future__ import annotations

import importlib

from pydantic import ValidationError
import pytest

import cryptotechnolog
import cryptotechnolog.config as config_module
import cryptotechnolog.config.settings as settings_module
from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus
from cryptotechnolog.core.global_instances import (
    get_event_bus,
    reset_event_bus,
    set_event_bus,
)


class TestImportTimeCleanup:
    """Регрессии для Step 4 Import-Time Cleanup."""

    def test_package_import_remains_safe_without_runtime_bootstrap(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Простой import пакета не должен зависеть от валидности runtime settings."""
        monkeypatch.setenv("DEBUG", "not-a-bool")

        reloaded_package = importlib.reload(cryptotechnolog)

        assert reloaded_package.__version__ == "1.7.0"

    def test_settings_module_reload_is_safe_until_explicit_access(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Перезагрузка settings-модуля не должна создавать Settings на import-time."""
        monkeypatch.setenv("DEBUG", "not-a-bool")

        reloaded_settings_module = importlib.reload(settings_module)

        with pytest.raises(ValidationError):
            reloaded_settings_module.get_settings()

    def test_config_module_reload_keeps_settings_access_lazy(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """config-пакет не должен форсировать settings bootstrap на import-time."""
        monkeypatch.setenv("DEBUG", "not-a-bool")

        importlib.reload(settings_module)
        reloaded_config_module = importlib.reload(config_module)

        with pytest.raises(ValidationError):
            reloaded_config_module.get_settings()

    def test_global_event_bus_requires_explicit_bootstrap(self) -> None:
        """Global EventBus getter не должен выполнять скрытую инициализацию."""
        reset_event_bus()

        with pytest.raises(RuntimeError, match="Global EventBus is not configured"):
            get_event_bus()

    def test_global_event_bus_can_be_set_explicitly(self) -> None:
        """Compatibility-accessor должен работать только после явного wiring."""
        reset_event_bus()
        bus = EnhancedEventBus(enable_persistence=False, redis_url=None, rate_limit=10000)

        try:
            set_event_bus(bus)
            assert get_event_bus() is bus
        finally:
            reset_event_bus()
