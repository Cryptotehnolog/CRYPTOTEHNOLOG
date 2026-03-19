import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from cryptotechnolog import main as main_module


class TestMain:
    """Тесты официального production entrypoint."""

    def test_main_function_exists(self) -> None:
        """Модуль должен экспортировать async main()."""
        assert hasattr(main_module, "main")
        assert asyncio.iscoroutinefunction(main_module.main)

    def test_main_module_imports(self) -> None:
        """Модуль должен импортироваться корректно."""
        assert hasattr(main_module, "asyncio")
        assert hasattr(main_module, "sys")
        assert hasattr(main_module, "run_production_runtime")

    def test_main_has_docstring(self) -> None:
        """main() должен иметь docstring."""
        assert main_module.main.__doc__ is not None
        assert "production entrypoint" in main_module.main.__doc__

    @pytest.mark.asyncio
    async def test_main_delegates_to_production_runtime(self) -> None:
        """main() должен делегировать запуск в production composition root."""
        with patch(
            "cryptotechnolog.main.run_production_runtime",
            new=AsyncMock(),
        ) as mock_run:
            await main_module.main()

        mock_run.assert_awaited_once()
