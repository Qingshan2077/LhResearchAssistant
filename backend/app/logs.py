"""Central Loguru configuration."""

import sys
from pathlib import Path

from loguru import logger

from app.config import settings

_configured = False


def setup_logging() -> None:
    """Configure console and rotating file sinks once per process."""
    global _configured
    if _configured:
        return

    log_dir = Path(settings.data_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.log_level.upper(),
        format=(
            "<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | "
            "<cyan>{name}</cyan>:{line} - {message}"
        ),
        colorize=True,
    )
    logger.add(
        log_dir / "research_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="1 day",
        retention="30 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {name}:{line} - {message}",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )
    logger.add(
        log_dir / "errors_{time:YYYY-MM-DD}.log",
        level="ERROR",
        rotation="1 day",
        retention="90 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {name}:{line} - {message}",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )
    _configured = True
    logger.info("Logging initialized. Log directory: {}", log_dir)
