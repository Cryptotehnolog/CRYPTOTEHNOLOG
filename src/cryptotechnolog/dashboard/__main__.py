"""CLI entrypoint для локального запуска dashboard backend слоя."""

from __future__ import annotations

import uvicorn

from cryptotechnolog.config import get_settings

from .app import create_dashboard_app


def main() -> None:
    """Запустить dashboard backend как отдельное FastAPI приложение."""
    settings = get_settings()
    uvicorn.run(
        create_dashboard_app(enable_canonical_runtime=True),
        host=settings.dashboard_host,
        port=settings.dashboard_port,
        access_log=False,
    )


if __name__ == "__main__":
    main()
