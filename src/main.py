# ==================== CRYPTOTEHNOLOG Main Entry Point ====================
# Institutional-Grade Crypto Trading Platform

import asyncio
import sys
from pathlib import Path

import structlog

from src.config.settings import get_settings

# Add src to path for imports
src_dir = Path(__file__).parent
sys.path.insert(0, str(src_dir.parent))


async def main() -> None:
    """Main application entry point."""
    # Load settings
    settings = get_settings()

    # Configure structured logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logger = structlog.get_logger()

    logger.info(
        "CRYPTOTEHNOLOG Platform Starting",
        environment=settings.environment,
        log_level=settings.log_level,
        version="1.0.0",
    )

    # TODO: Implement main application logic here
    # This is a placeholder for the actual trading platform initialization

    logger.info("CRYPTOTEHNOLOG Platform initialized successfully")

    # For now, just keep the container running
    try:
        while True:
            await asyncio.sleep(60)
            logger.debug("Heartbeat")
    except asyncio.CancelledError:
        logger.info("Received shutdown signal, shutting down gracefully")
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
    finally:
        logger.info("CRYPTOTEHNOLOG Platform stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
