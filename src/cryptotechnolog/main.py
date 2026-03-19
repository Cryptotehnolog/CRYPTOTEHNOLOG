# ==================== CRYPTOTEHNOLOG Main Entry Point ====================
# Institutional-Grade Crypto Trading Platform

import asyncio
import sys

from cryptotechnolog.bootstrap import run_production_runtime
from cryptotechnolog.runtime_identity import get_release_identity


async def main() -> None:
    """Официальная production entrypoint-функция платформы."""
    await run_production_runtime()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        release_identity = get_release_identity()
        print(
            f"{release_identity.project_name} {release_identity.version} критическая ошибка: {e}",
            file=sys.stderr,
        )
        sys.exit(1)
